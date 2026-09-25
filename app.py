from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import os
import hashlib
import json
import datetime
from groq import Groq

app = Flask(__name__)
app.secret_key = "super_secret_finance_key"

# Groq API Setup
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)

if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-key.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

def hash_pass(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def get_totals(username):
    now = datetime.datetime.now()
    expenses_ref = db.collection("expenses").where("username", "==", username).stream()
    
    daily_total, weekly_total, monthly_total = 0, 0, 0
    for exp in expenses_ref:
        data = exp.to_dict()
        exp_date = data.get("timestamp")
        if not exp_date:
            continue
        exp_date = exp_date.replace(tzinfo=None)
        
        tx_type = data.get("type", "expense")
        if tx_type != "expense":
            continue
            
        try:
            amt = float(data.get("amount", 0))
        except (ValueError, TypeError):
            amt = 0
            
        if exp_date.date() == now.date():
            daily_total += amt
        if exp_date.isocalendar()[1] == now.isocalendar()[1] and exp_date.year == now.year:
            weekly_total += amt
        if exp_date.month == now.month and exp_date.year == now.year:
            monthly_total += amt
            
    return daily_total, weekly_total, monthly_total

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
    if 'username' not in session:
        return redirect(url_for('home'))
    daily_total, weekly_total, monthly_total = get_totals(session['username'])
    return render_template('dashboard.html', username=session['username'], daily=daily_total, weekly=weekly_total, monthly=monthly_total)

@app.route('/details/<period>')
def details(period):
    if 'username' not in session:
        return redirect(url_for('home'))
    now = datetime.datetime.now()
    expenses_ref = db.collection("expenses").where("username", "==", session['username']).stream()
    
    filtered_exp = []
    total_income = 0
    total_expense = 0
    
    for exp in expenses_ref:
        data = exp.to_dict()
        exp_date = data.get("timestamp")
        if not exp_date:
            continue
        exp_date = exp_date.replace(tzinfo=None)
        data['_sort_time'] = exp_date
        
        match = False
        if period == 'daily' and exp_date.date() == now.date():
            match = True
        elif period == 'weekly' and exp_date.isocalendar()[1] == now.isocalendar()[1] and exp_date.year == now.year:
            match = True
        elif period == 'monthly' and exp_date.month == now.month and exp_date.year == now.year:
            match = True
        
        if match:
            tx_type = data.get("type", "expense")
            data["type"] = tx_type
            filtered_exp.append(data)
            try:
                amt = float(data.get("amount", 0))
                if tx_type == 'income':
                    total_income += amt
                else:
                    total_expense += amt
            except (ValueError, TypeError):
                pass

    filtered_exp.sort(key=lambda x: x['_sort_time'], reverse=True)
    net_balance = total_income - total_expense
            
    return render_template(
        'details.html',
        period=period.capitalize(),
        expenses=filtered_exp,
        total_income=total_income,
        total_expense=total_expense,
        balance=net_balance
    )

@app.route('/api/chat', methods=['POST'])
def api_chat():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user_input = request.json.get('text', '')
    ai_lang = request.json.get('lang', 'English')
    
    if ai_lang == 'Bengali':
        lang_instruction = "You MUST write 'reply_message' and 'category' strictly in Bengali script (বাংলা হরফে)."
    elif ai_lang == 'Hindi':
        lang_instruction = "You MUST write 'reply_message' and 'category' strictly in Hindi Devanagari script (हिंदी में)."
    else:
        lang_instruction = "You MUST write 'reply_message' and 'category' strictly in English."
    
    prompt = f"""
    User message: "{user_input}"
    Selected Language: {ai_lang}
    
    Task:
    1. Extract any financial transactions (expenses or income) mentioned by the user into the "transactions" array.
       Each object MUST have:
       - "category": Item/expense name written strictly in {ai_lang}
       - "category_en": Item/expense name in English (e.g., "Fish")
       - "category_bn": Item/expense name in Bengali script (e.g., "মাছ")
       - "category_hi": Item/expense name in Hindi script (e.g., "मछली")
       - "amount": Numeric value only
       - "type": strictly "income" (if money received/salary/earned) OR "expense" (if money spent/bought/paid).
       If no transaction is mentioned, keep "transactions" as [].
    2. {lang_instruction}
    3. Make "reply_message" a friendly, natural conversational reply in {ai_lang} and end with a short follow-up question.
    
    Return ONLY valid JSON in this exact format:
    {{
      "transactions": [
        {{
          "category": "Name in {ai_lang}",
          "category_en": "Fish",
          "category_bn": "মাছ",
          "category_hi": "मछली",
          "amount": 500,
          "type": "expense"
        }}
      ],
      "reply_message": "Your interactive reply + follow-up question strictly in {ai_lang}"
    }}
    """
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": f"You are a live conversational AI Finance Agent. {lang_instruction} Output pure JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="openai/gpt-oss-20b",
            response_format={"type": "json_object"}
        )
        
        ai_data = json.loads(chat_completion.choices[0].message.content)
        
        transactions = ai_data.get("transactions", ai_data.get("expenses", []))
        reply = ai_data.get("reply_message", "Done!")
        
        for item in transactions:
            cat = item.get("category")
            amt = item.get("amount")
            tx_type = item.get("type", "expense").lower()
            if tx_type not in ["income", "expense"]:
                tx_type = "expense"
                
            if cat and amt is not None:
                try:
                    numeric_amt = float(amt)
                    db.collection("expenses").document().set({
                        "username": session['username'],
                        "category": cat,
                        "category_en": item.get("category_en", cat),
                        "category_bn": item.get("category_bn", cat),
                        "category_hi": item.get("category_hi", cat),
                        "amount": numeric_amt,
                        "type": tx_type,
                        "date_str": datetime.datetime.now().strftime("%d %b %Y, %I:%M %p"),
                        "timestamp": firestore.SERVER_TIMESTAMP
                    })
                except (ValueError, TypeError):
                    pass
                    
        daily, weekly, monthly = get_totals(session['username'])
        
        return jsonify({
            "reply": reply,
            "daily": daily,
            "weekly": weekly,
            "monthly": monthly
        })
    except Exception as e:
        print(f"Groq Error: {e}")
        return jsonify({"reply": f"API Error: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
