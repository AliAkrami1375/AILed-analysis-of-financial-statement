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

@app.route('/api/search', methods=['POST'])
@token_required
def search():
    data = request.get_json()
    company = data.get('company_name')
    year = str(data.get('fiscal_year'))
    if not company or not year:
        return jsonify({'error': 'Missing parameters'}), 400

    cache = load_json('search_cache.json')
    archive = load_json('archive.json')
    config = load_json('config.json')
    cache_key = f"{company}_{year}"

    if cache_key in cache:
        result = cache[cache_key]
    else:
        df = pd.read_csv('data.csv')
        filtered = df[
            (df['year'].astype(str) == year) &
            (df['full_report_sentence'].str.contains(company, case=False, na=False))
        ]
        if filtered.empty:
            return jsonify({'error': 'Data not found'}), 404
        record = filtered.iloc[0].to_dict()
        fields = config.get('fields', [])
        field_lines = "\n".join(f"{key}: {record.get(key, 'N/A')}" for key in fields)
        prompt = f"{config.get('default_prompt', '')}\nAnalyze {company} in {year}.\n{field_lines}"
        client = OpenAI(api_key=config.get("openai_api_key"))
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": config.get('default_prompt', '')},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )
        analysis = response.choices[0].message.content
        result = {
            'summary': analysis,
            'raw_data': record
        }
        cache[cache_key] = result
        save_json('search_cache.json', cache)

    user = request.user
    if user not in archive:
        archive[user] = []
    archive[user].append({
        'company_name': company,
        'fiscal_year': year,
        'result': result
    })
    save_json('archive.json', archive)
    return jsonify({'result': result})

@app.route('/api/archive', methods=['GET'])
@token_required
def archive():
    user = request.user
    data = load_json('archive.json')
    return jsonify({'archive': data.get(user, [])})

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
