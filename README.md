# 🧠 AI Chatbot with Web Scraping & Hugging Face Integration

This project is a smart *AI Chatbot* that automatically *scrapes data from any website* and uses the *Hugging Face API* to generate contextual responses.  
It was developed as part of the *Relinns Technologies Internship Task*.

---  
https://youtu.be/2ab9EEBZbto?si=NWEFHuJrKRRqzqYc
## 🚀 Features 

- 🌐 *Website Scraping* — Extracts and parses data from any given URL using BeautifulSoup.
- 💬 *Smart Chatbot* — Uses Hugging Face models to give human-like, context-aware answers.
- 🧾 *Context Memory* — Stores website content and products locally in the cached_contexts folder.
- ⚡ *Lightweight* — Runs directly from terminal, no complex setup needed.
- 🔑 *Customizable API Key* — Uses Hugging Face token for secure model access.

---

## 🛠 Tech Stack

| Component | Technology Used |
|------------|-----------------|
| Language | Python 3.12+ |
| Web Scraping | requests, beautifulsoup4 |
| AI Model | huggingface_hub |
| Storage | Local text & JSON files |
| Environment | venv (Python virtual environment) |

---

## ⚙ Setup Instructions

### 1️⃣ Clone or Download the Project
```bash
git clone www.github.com/abhishekdeyz
cd abhishek_chatbot

2️⃣ Create and Activate Virtual Environment
python -m venv venv
venv\Scripts\activate

3️⃣ Install Required Libraries
pip install requests beautifulsoup4 huggingface_hub

4️⃣ Add Your Hugging Face API Key
	•	Open main.py
	•	Replace this line:
    API_URL = "YOUR_HUGGINGFACE_MODEL_URL"
API_KEY = "YOUR_HUGGINGFACE_API_KEY"


🌐 Website Scraping

To scrape any website, run:

python main.py --scrape --url "https://botpenguin.com"


🤖 Running the Chatbot

Once scraping is done, start the chatbot:

python main.py


User: What is BotPenguin?
Bot: Description: BotPenguin’s Chatbot Maker & Live Chat for Website, WhatsApp, Facebook, Instagram & Telegram Generate 10x more leads Solve 80% more queries Engage 70% more visitors Earn 90% more revenue Get Started FREE FREE Forever Plan. No Credit Card Required.
Link: https://app.botpenguin.com/authentication?signup=1&u=https://botpenguin.com/
