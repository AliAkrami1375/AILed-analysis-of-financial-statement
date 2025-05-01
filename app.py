from flask import Flask, request, jsonify, render_template
import jwt
import datetime
import json
import os
import pandas as pd
from functools import wraps
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
CORS(app)

# Utilities

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

# JWT Decorator

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            bearer = request.headers['Authorization']
            if bearer.startswith('Bearer '):
                token = bearer[7:]

        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            request.user = data['username']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        return f(*args, **kwargs)
    return decorated

# Routes

@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    config = load_json('config.json')
    users = config.get('users', [])

    for user in users:
        if user['username'] == username and user['password'] == password:
            token = jwt.encode({
                'username': username,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=2)
            }, app.config['SECRET_KEY'], algorithm='HS256')
            return jsonify({'token': token})

    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/search', methods=['POST'])
@token_required
def search():
    data = request.get_json()
    company = data.get("company_name")
    year = str(data.get("fiscal_year"))

    if not company or not year:
        return jsonify({"error": "Missing company name or fiscal year"}), 400

    cache = load_json("search_cache.json")
    archive = load_json("archive.json")
    config = load_json("config.json")

    cache_key = f"{company}_{year}"

    if cache_key in cache:
        result = cache[cache_key]
    else:
        df = pd.read_csv("data.csv")
        row = df[(df['company_name'] == company) & (df['fiscal_year'].astype(str) == year)]

        if row.empty:
            return jsonify({"error": "Data not found"}), 404

        record = row.iloc[0].to_dict()

        fields = config.get("fields", ["revenue", "profit", "assets"])
        field_lines = "\n".join(f"{key.capitalize()}: {record.get(key, 'N/A')}" for key in fields)

        prompt = (
            config.get("default_prompt", "You are a financial analyst.") + "\n" +
            f"Analyze the financial performance of {company} in fiscal year {year}.\n" +
            field_lines + "\nReturn a short paragraph analysis."
        )

        client = OpenAI(api_key=config.get("openai_api_key"))
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": config.get("default_prompt", "You are a financial analyst.")},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )

        analysis = response.choices[0].message.content

        result = {
            "summary": analysis,
            "raw_data": record
        }

        cache[cache_key] = result
        save_json("search_cache.json", cache)

    user = request.user
    if user not in archive:
        archive[user] = []
    archive[user].append({
        "company_name": company,
        "fiscal_year": year,
        "result": result
    })
    save_json("archive.json", archive)

    return jsonify({"result": result})

@app.route('/api/archive', methods=['GET'])
@token_required
def get_archive():
    archive = load_json("archive.json")
    user = request.user
    return jsonify({"archive": archive.get(user, [])})

@app.route('/api/config', methods=['GET', 'POST'])
@token_required
def manage_config():
    config = load_json("config.json")
    if request.method == 'GET':
        return jsonify({
            "openai_api_key": config.get("openai_api_key"),
            "default_prompt": config.get("default_prompt"),
            "fields": config.get("fields", []),
            "users": config.get("users", [])
        })
    if request.user != 'admin':
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json()
    config["openai_api_key"] = data.get("openai_api_key", config.get("openai_api_key"))
    config["default_prompt"] = data.get("default_prompt", config.get("default_prompt"))
    config["fields"] = data.get("fields", config.get("fields", []))
    save_json("config.json", config)
    return jsonify({"success": True})

@app.route('/api/users', methods=['POST', 'DELETE'])
@token_required
def manage_users():
    if request.user != 'admin':
        return jsonify({"error": "Forbidden"}), 403

    config = load_json("config.json")
    users = config.get("users", [])

    data = request.get_json()
    username = data.get("username")

    if request.method == 'POST':
        password = data.get("password")
        if any(u['username'] == username for u in users):
            return jsonify({"error": "User already exists"}), 400
        users.append({"username": username, "password": password})
    elif request.method == 'DELETE':
        if username == 'admin':
            return jsonify({"error": "Cannot delete admin"}), 400
        users = [u for u in users if u['username'] != username]

    config["users"] = users
    save_json("config.json", config)
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(debug=True)