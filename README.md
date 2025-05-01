# Flask Dashboard App

A lightweight dashboard app built with Flask, JWT authentication, and OpenAI integration — using CSV and JSON files instead of a database.

---

## 🚀 Features
- JWT-based login system (with credentials from `config.json`)
- Role-based UI (admin vs user)
- Responsive dashboard with mobile hamburger menu
- Search tab: query company data from `data.csv`
- Archive tab: cached results per user
- Settings tab (admin only):
  - Manage OpenAI key
  - Customize GPT prompt
  - Add/remove fields for GPT input
  - Manage users (except admin)
- ChatGPT integration with prompt customization

---

## 🛠 Setup Instructions

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd your-project-folder
```

### 2. Create and activate a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
```

### 3. Install required packages
```bash
pip install -r requirements.txt
```

### 4. Required Files
Make sure the following files exist:

- `data.csv` — your dataset with columns like: `company_name`, `fiscal_year`, `revenue`, `profit`, etc.
- `config.json` — basic structure:
```json
{
  "openai_api_key": "your-openai-key",
  "default_prompt": "You are a financial analyst.",
  "fields": ["revenue", "profit", "assets"],
  "users": [
    { "username": "admin", "password": "your-password" }
  ]
}
```

### 5. Run the Flask app
```bash
python app.py
```

App will be available at: `http://127.0.0.1:5000/`

---

## 📂 File Structure (Important Files)
```
├── app.py
├── data.csv
├── config.json
├── archive.json
├── search_cache.json
├── requirements.txt
├── templates/
│   ├── login.html
│   └── dashboard.html
├── static/
│   └── js/
│       ├── login.js
│       └── dashboard.js
```

---

## 📌 Notes
- No database is used — all data is stored in JSON files.
- If `data.csv` is large, consider converting it to pre-indexed JSON or optimize using chunking.
- Only admin can see and use the Settings tab.

---

## 🔐 Default Login
```
Username: admin
Password: your-password
```