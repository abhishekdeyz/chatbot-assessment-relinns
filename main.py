#!/usr/bin/env python3
"""
Relinns assessment - single-file solution
Usage:
  python main.py --scrape --url "https://botpenguin.com"
  python main.py --chat  --url "https://botpenguin.com"

Before chat: set HF_API_KEY below to your Hugging Face token (hf_...)
"""
import requests, os, json, re, argparse, time
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# ---------------- CONFIG ----------------
CACHE_FOLDER = "cached_contexts"
HF_API_KEY = "hf_xxxxxxxxxxxxxxxxxxxxxxx"
MODEL_URL = "https://api-inference.huggingface.co/models/google/flan-t5-small"  # or any small QA model
MAX_CONTEXT_CHARS = 3000
HEADERS = {"User-Agent":"Mozilla/5.0"}
# ----------------------------------------

def ensure_folder():
    if not os.path.exists(CACHE_FOLDER):
        os.makedirs(CACHE_FOLDER)

def domain_files(url):
    parsed = urlparse(url)
    name = parsed.netloc.replace(":", "_")
    text_file = os.path.join(CACHE_FOLDER, f"{name}_context.txt")
    json_file = os.path.join(CACHE_FOLDER, f"{name}_products.json")
    return text_file, json_file

def clean_text(s):
    return re.sub(r'\s+', ' ', s).strip()

def fetch_url(url, timeout=20):
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r

def extract_text_html(html):
    soup = BeautifulSoup(html, "html.parser")
    texts = []
    # collect main textual tags in order
    for tag in soup.find_all(["h1","h2","h3","p","li"]):
        t = clean_text(tag.get_text())
        if len(t) >= 30:
            texts.append(t)
    # hero first if exists
    hero = ""
    h1 = soup.find("h1")
    if h1:
        hero = clean_text(h1.get_text())
    content = ""
    if hero:
        content += "HERO: " + hero + "\n\n"
    content += "\n".join(texts[:400])
    return clean_text(content)

# Heuristic: find product/item blocks and try to extract title, price, link, description
def extract_products_html(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    candidate_selectors = [
        "[class*='product']","[class*='Product']","[class*='item']","[class*='card']",
        "[class*='listing']","[id*='product']"
    ]
    found = []
    seen_texts = set()

    # collect candidate blocks
    blocks = []
    for sel in candidate_selectors:
        blocks.extend(soup.select(sel))

    # also use article tags
    blocks.extend(soup.find_all("article"))
    # fallback: find repeated structures - tags with many children
    if not blocks:
        blocks = soup.find_all(["div","section"], limit=80)

    price_re = re.compile(r'₹\s?\d[\d,]|Rs\.?\s?\d[\d,]|\$\s?\d[\d,]|\d[\d,]\s?INR', re.I)

    for b in blocks:
        # title: look for h2/h3 or strong inside block
        title_tag = b.find(["h1","h2","h3","h4","strong"])
        title = clean_text(title_tag.get_text()) if title_tag else ""
        # price: search within block text
        block_text = clean_text(b.get_text(" ", strip=True))
        price_match = price_re.search(block_text)
        price = price_match.group(0) if price_match else ""
        # description: first 150 chars excluding title
        desc = ""
        if title:
            desc = block_text.replace(title, "", 1).strip()[:300]
        else:
            desc = block_text[:300]
        # link: find first <a> with href
        link_tag = b.find("a", href=True)
        link = ""
        if link_tag:
            href = link_tag['href']
            if href.startswith("http"):
                link = href
            else:
                # make absolute
                link = requests.compat.urljoin(base_url, href)
        # if minimal meaningful text and not duplicate
        key = (title or desc)[:120]
        if key and key not in seen_texts and (len(title) > 3 or len(desc) > 30):
            seen_texts.add(key)
            found.append({"title": title, "price": price, "description": desc, "link": link})
    # attempt to dedupe by title
    dedup = []
    titles = set()
    for f in found:
        t = f.get("title","").lower()
        if t in titles and t != "":
            continue
        titles.add(t)
        dedup.append(f)
    return dedup

def save_context_and_products(text, products, text_file, json_file):
    if len(text) > MAX_CONTEXT_CHARS:
        text = text[:MAX_CONTEXT_CHARS] + "..."
    with open(text_file, "w", encoding="utf-8") as f:
        f.write(text)
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    print(f"[+] context -> {text_file} ({len(text)} chars)")
    print(f"[+] products -> {json_file} ({len(products)} items)")

def scrape_url(url):
    ensure_folder()
    text_file, json_file = domain_files(url)
    print("[*] Fetching URL:", url)
    r = fetch_url(url)
    content_type = r.headers.get("content-type","")
    html = r.text
    # detect pdf
    if "application/pdf" in content_type.lower():
        print("[!] PDF detected - not implemented auto-extract in this script. Download manually and paste text into context file.")
        return text_file, json_file
    # parse html
    print("[*] Parsing HTML...")
    text = extract_text_html(html)
    products = extract_products_html(html, url)
    # if no products found, products may be in different pages - try scanning links for /product or /shop etc (light)
    if not products:
        print("[i] No product blocks found heuristically. Scanning page links for likely product pages (limited)...")
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a['href']
            if any(word in href.lower() for word in ["/product", "/shop", "/item", "/catalog", "productid", "/collections"]):
                full = requests.compat.urljoin(url, href)
                if full not in links:
                    links.append(full)
            if len(links) >= 6:
                break
        for lnk in links:
            try:
                rr = fetch_url(lnk)
                pr = extract_products_html(rr.text, url)
                if pr:
                    products.extend(pr)
                time.sleep(0.6)
            except Exception:
                pass
    save_context_and_products(text, products, text_file, json_file)
    return text_file, json_file

# ---------------- Retrieval & HF query ----------------
def simple_retrieve(context, query, chunk_size=900):
    chunks = [context[i:i+chunk_size] for i in range(0, len(context), chunk_size)]
    qwords = [w.lower() for w in re.findall(r'\w+', query) if len(w)>2]
    best_idx, best_score = 0, -1
    for i,c in enumerate(chunks):
        lc = c.lower()
        score = sum(1 for w in qwords if w in lc)
        if score > best_score:
            best_score = score
            best_idx = i
    return chunks[best_idx] if chunks else context

def build_prompt(context_chunk, user_question):
    prompt = (
        "You are a helpful assistant. Use ONLY the website context below to answer the user's question. "
        "If the answer is not present in the context say 'I couldn't find that on the website.' Keep the answer concise.\n\n"
        f"Website context:\n{context_chunk}\n\nUser: {user_question}\nAssistant:"
    )
    return prompt

def hf_query(prompt, max_tokens=200):
    if not HF_API_KEY or HF_API_KEY == "hf_xxx":
        return "ERROR: Set HF_API_KEY in the script before chat."
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": prompt, "parameters": {"max_new_tokens": max_tokens, "temperature": 0.2}}
    try:
        r = requests.post(MODEL_URL, headers=headers, json=payload, timeout=60)
    except Exception as e:
        return f"ERROR: request failed: {e}"
    if r.status_code != 200:
        return f"ERROR: HF returned {r.status_code}: {r.text}"
    try:
        data = r.json()
        if isinstance(data, list) and isinstance(data[0], dict) and "generated_text" in data[0]:
            return data[0]["generated_text"].strip()
        if isinstance(data, dict) and "generated_text" in data:
            return data["generated_text"].strip()
        return str(data)
    except Exception as e:
        return f"ERROR: parse failed: {e}"

# ---------------- Chat logic: structured lookup first ----------------
def load_json(json_file):
    if os.path.exists(json_file):
        with open(json_file, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def find_product_by_name(products, q):
    qlow = q.lower()
    # look for exact price query patterns: "price of X" or "how much is X"
    # check each product title and description similarity by substring
    matches = []
    for p in products:
        title = (p.get("title") or "").lower()
        desc = (p.get("description") or "").lower()
        if qlow in title or qlow in desc or any(word in title for word in qlow.split()):
            matches.append(p)
    # also fuzzy try: check if any product words appear
    if not matches:
        for p in products:
            title = (p.get("title") or "").lower()
            score = sum(1 for w in qlow.split() if w in title)
            if score >= 1:
                matches.append(p)
    return matches

def chat_mode(url):
    text_file, json_file = domain_files(url)
    if not os.path.exists(text_file):
        print("[!] Context not found. Run --scrape first.")
        return
    context = open(text_file, "r", encoding="utf-8").read()
    products = load_json(json_file)
    print("[+] Loaded context and products. Start chat (type exit).")
    while True:
        q = input("\nYou: ").strip()
        if q.lower() in ("exit","quit"):
            print("Bye.")
            break
        # structured intent detection: look for price / cost / how much / available / details
        if any(k in q.lower() for k in ["price", "cost", "how much", "price of", "rate", "₹", "rs ", "rs.", "rupees"]):
            # try extract product name after 'price of' etc
            # simple heuristic: remove question words
            # find product matches
            # try direct pattern: "price of <name>"
            m = re.search(r'price of (.+)', q.lower())
            search_key = m.group(1).strip() if m else q.lower()
            matches = find_product_by_name(products, search_key)
            if matches:
                # print top 3 matches succinctly
                out_lines = []
                for p in matches[:5]:
                    t = p.get("title") or "Item"
                    pr = p.get("price") or "Price not found"
                    lk = p.get("link") or ""
                    out_lines.append(f"{t} — {pr}" + (f" (link: {lk})" if lk else ""))
                print("\nBot (from scraped data):\n" + "\n".join(out_lines))
                continue
            else:
                # fallback to retrieval+HF
                chunk = simple_retrieve(context, q)
                prompt = build_prompt(chunk, q)
                ans = hf_query(prompt)
                print("\nBot:", ans)
                continue
        # if question mentions product name explicitly, try product lookup
        matches = find_product_by_name(products, q)
        if matches:
            # reply with structured info
            p = matches[0]
            t = p.get("title") or "Item"
            pr = p.get("price") or "Price not found"
            desc = p.get("description") or ""
            lk = p.get("link") or ""
            resp = f"{t}\nPrice: {pr}\n{('Description: ' + desc) if desc else ''}\n{('Link: ' + lk) if lk else ''}"
            print("\nBot (from scraped data):\n" + resp)
            continue
        # otherwise retrieval + HF
        chunk = simple_retrieve(context, q)
        prompt = build_prompt(chunk, q)
        ans = hf_query(prompt)
        print("\nBot:", ans)

# ---------------- CLI ----------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scrape", action="store_true")
    parser.add_argument("--chat", action="store_true")
    parser.add_argument("--url", type=str, help="URL to scrape / chat with")
    args = parser.parse_args()

    if args.scrape:
        if not args.url:
            url = input("Enter URL to scrape: ").strip()
        else:
            url = args.url
        if not url:
            print("No URL provided. Exiting.")
            return
        scrape_url(url)
    elif args.chat:
        if not args.url:
            url = input("Enter URL whose context to use: ").strip()
        else:
            url = args.url
        if not url:
            print("No URL provided. Exiting.")
            return
        chat_mode(url)
    else:
        print("Usage:\n  python main.py --scrape --url <URL>\n  python main.py --chat  --url <URL>")

if __name__ == "__main__":
    main()