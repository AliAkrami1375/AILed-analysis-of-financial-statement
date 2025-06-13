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

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
        if not token:
            return jsonify({'error': 'Token missing'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            request.user = data['username']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/login', methods=['POST'])
def login():
    credentials = request.get_json()
    username = credentials.get('username')
    password = credentials.get('password')
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

# UPDATED app.py to compute ratios using reshaped_data.csv and Ratio.xlsx

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
    print("[LOG] Cache Key:", cache_key)

    if cache_key in cache:
        print("[LOG] Cache hit for", cache_key)
        result = cache[cache_key]
    else:
        df = pd.read_csv("data.csv")
        row = df[(df['MNEMONIC'].str.lower().str.strip() == company.lower().strip()) & (df['year'].astype(str) == year)]

        if row.empty:
            print("[LOG] No match in data.csv, continuing with reshaped_data only")
            record = {"MNEMONIC": company, "year": year}
            symbol = company  # fallback
        else:
            record = row.iloc[0].to_dict()
            print("[LOG] Loaded record:", record)
            symbol = record.get("MNEMONIC")
            if not symbol:
                return jsonify({"error": "Symbol not found in data"}), 404
            symbol = symbol.strip().rstrip('.')

        fields = config.get("fields", [])
        field_lines = "\n".join(f"{key.capitalize()}: {record.get(key, 'N/A')}" for key in fields)

        ratios_df = pd.read_excel("Ratio.xlsx")
        reshape_df = pd.read_csv("reshaped_data.csv")
        reshape_df = reshape_df[(reshape_df['Symbol'] == symbol) & (reshape_df['year'].astype(str) == year)]
        metric_values = reshape_df.set_index("Financial Metrics")["amount"].to_dict()

        from collections import defaultdict
        computed_ratios = []
        category_ratios = defaultdict(list)

        for _, row in ratios_df.iterrows():
            formula = str(row.get("Formula"))
            ratio_name = row.get("Ration")
            category = row.get("Category")
            if pd.isna(formula) or '[' in formula or ']' in formula:
                continue

            try:
                temp_formula = formula
                for metric in metric_values:
                    temp_formula = temp_formula.replace(metric, str(metric_values[metric]))
                value = eval(temp_formula)
                ratio_data = {
                    "ratio": ratio_name,
                    "category": category,
                    "formula": formula,
                    "evaluated": temp_formula,
                    "value": value
                }
                computed_ratios.append(ratio_data)
                category_ratios[category].append(ratio_data)
            except Exception as e:
                computed_ratios.append({
                    "ratio": ratio_name,
                    "category": category,
                    "formula": formula,
                    "evaluated": temp_formula,
                    "error": str(e)
                })

        client = OpenAI(api_key=config.get("openai_api_key"))
        category_summaries = {}

        for category, ratios in category_ratios.items():
            ratios_text = "\n".join(f"- {r['ratio']}: {r['value']}" for r in ratios if 'value' in r)
            cat_prompt = (
                f"You are a financial analyst. Analyze the company's performance in the category of '{category}'.\n"
                f"The following ratios were calculated:\n{ratios_text}\n\n"
                f"Provide a concise 10-line summary of what this indicates about the company's financial health in this category."
            )
            response = client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": "You are a financial analyst."},
                    {"role": "user", "content": cat_prompt}
                ],
                temperature=0.7,
                max_tokens=250
            )
            category_summaries[category] = response.choices[0].message.content

        overall_prompt = (
            config.get("default_prompt", "You are a financial analyst.") + "\n" +
            f"Analyze the overall financial performance of {company} in fiscal year {year}.\n" +
            field_lines + "\n\n" +
            "All Ratios computed:\n" +
            "\n".join(f"- {r['ratio']}: {r.get('value', 'Error')}" for r in computed_ratios if 'value' in r)
        )
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": config.get("default_prompt", "You are a financial analyst.")},
                {"role": "user", "content": overall_prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )
        overall_summary = response.choices[0].message.content

        result = {
            "summary": overall_summary,
            "category_summaries": category_summaries,
            "raw_data": record,
            "ratios": computed_ratios
        }

        cache[cache_key] = result
        save_json("search_cache.json", cache)

    if not any(item["company_name"] == company and str(item["fiscal_year"]) == year for item in archive):
        archive.append({
            "company_name": company,
            "fiscal_year": year,
            "result": result
        })
        save_json("archive.json", archive)

    return jsonify({"result": result})




@app.route('/api/archive', methods=['GET'])
@token_required
def archive():
    user = request.user
    data = load_json('archive.json')
    return jsonify({'archive': data})

@app.route('/api/config', methods=['GET', 'POST'])
@token_required
def config():
    current = load_json('config.json')
    if request.method == 'GET':
        return jsonify({
            'openai_api_key': current.get('openai_api_key'),
            'default_prompt': current.get('default_prompt'),
            'fields': current.get('fields', []),
            'users': current.get('users', [])
        })
    if request.user != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    incoming = request.get_json()
    current['openai_api_key'] = incoming.get('openai_api_key', current.get('openai_api_key'))
    current['default_prompt'] = incoming.get('default_prompt', current.get('default_prompt'))
    current['fields'] = incoming.get('fields', current.get('fields', []))
    save_json('config.json', current)
    return jsonify({'success': True})

@app.route('/api/users', methods=['POST', 'DELETE'])
@token_required
def users():
    if request.user != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    config = load_json('config.json')
    users = config.get('users', [])
    data = request.get_json()
    username = data.get('username')
    if request.method == 'POST':
        password = data.get('password')
        if any(u['username'] == username for u in users):
            return jsonify({'error': 'User already exists'}), 400
        users.append({'username': username, 'password': password})
    elif request.method == 'DELETE':
        if username == 'admin':
            return jsonify({'error': 'Cannot delete admin'}), 400
        users = [u for u in users if u['username'] != username]
    config['users'] = users
    save_json('config.json', config)
    return jsonify({'success': True})

@app.route('/api/companies')
@token_required
def companies():
    df = pd.read_csv('data.csv')
    names = df['full_report_sentence'].dropna().tolist()
    candidates = {line.split()[0] for line in names if len(line.split()) > 0}
    return jsonify({'companies': sorted(candidates)})

if __name__ == '__main__':
    app.run(debug=True)
