from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai
import datetime
import os
import hashlib
import json

app = Flask(__name__)
app.secret_key = "super_secret_finance_key"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # JSON format mandatory
    model = genai.GenerativeModel('gemini-pro', generation_config={"response_mime_type": "application/json"})

if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-key.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

def hash_pass(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('auth.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    user = db.collection("users").document(email).get()
    if user.exists and user.to_dict().get("password") == hash_pass(password):
        session['username'] = email
        return redirect(url_for('dashboard'))
    flash("Invalid email or password.")
    return redirect(url_for('home'))

@app.route('/register', methods=['POST'])
def register():
    email = request.form.get('email')
    password = request.form.get('password')
    if db.collection("users").document(email).get().exists:
        flash("Account already exists with this email!")
    else:
        db.collection("users").document(email).set({"password": hash_pass(password)})
        session['username'] = email
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'username' not in session: return redirect(url_for('home'))
    now = datetime.datetime.now()
    expenses_ref = db.collection("expenses").where("username", "==", session['username']).stream()
    
    daily_total, weekly_total, monthly_total = 0, 0, 0
    for exp in expenses_ref:
        data = exp.to_dict()
        exp_date = data.get("timestamp")
        if not exp_date: continue
        exp_date = exp_date.replace(tzinfo=None)
        amt = float(data.get("amount", 0))
        if exp_date.date() == now.date(): daily_total += amt
        if exp_date.isocalendar()[1] == now.isocalendar()[1] and exp_date.year == now.year: weekly_total += amt
        if exp_date.month == now.month and exp_date.year == now.year: monthly_total += amt

    return render_template('dashboard.html', username=session['username'], daily=daily_total, weekly=weekly_total, monthly=monthly_total)

@app.route('/details/<period>')
def details(period):
    if 'username' not in session: return redirect(url_for('home'))
    now = datetime.datetime.now()
    expenses_ref = db.collection("expenses").where("username", "==", session['username']).order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
    
    filtered_exp = []
    total = 0
    for exp in expenses_ref:
        data = exp.to_dict()
        exp_date = data.get("timestamp")
        if not exp_date: continue
        exp_date = exp_date.replace(tzinfo=None)
        
        match = False
        if period == 'daily' and exp_date.date() == now.date(): match = True
        elif period == 'weekly' and exp_date.isocalendar()[1] == now.isocalendar()[1] and exp_date.year == now.year: match = True
        elif period == 'monthly' and exp_date.month == now.month and exp_date.year == now.year: match = True
        
        if match:
            filtered_exp.append(data)
            total += float(data.get("amount", 0))
            
    return render_template('details.html', period=period.capitalize(), expenses=filtered_exp, total=total)

@app.route('/api/chat', methods=['POST'])
def api_chat():
    if 'username' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    user_input = request.json.get('text')
    ai_lang = request.json.get('lang', 'English') 
    
    prompt = f"""
    Extract the expenses from the user's input: "{user_input}"
    Return a JSON object with exactly two keys:
    1. "expenses": A list of objects with "category" and "amount". (Keep empty [] if no expense is found or if the user is just greeting like 'Hi').
    2. "reply_message": A friendly conversational response in {ai_lang} language acknowledging what was saved, or a friendly greeting/response if they just said "Hi" or something else.
    Do not use markdown blocks like ```json.
    """
    
    try:
        response = model.generate_content(prompt)
        # Markdown backticks thakle seta remove korar jonno
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        ai_data = json.loads(clean_text)
        
        expenses = ai_data.get("expenses", [])
        reply = ai_data.get("reply_message", "Processed successfully.")
        
        for item in expenses:
            cat = item.get("category")
            amt = item.get("amount")
            if cat and amt:
                db.collection("expenses").document().set({
                    "username": session['username'],
                    "category": cat,
                    "amount": amt,
                    "date_str": datetime.datetime.now().strftime("%d %b %Y, %I:%M %p"),
                    "timestamp": firestore.SERVER_TIMESTAMP
                })
        return jsonify({"reply": reply})
    except Exception as e:
        # Asol error ta return korchi jate apni screen-ei dekhte pan
        print(f"Chat Error: {e}") 
        return jsonify({"reply": f"API Error: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
