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
def ai_chat():
    if 'user' not in session:
        return jsonify({"reply": "Please login first."}), 401

    user_email = session['user']
    data = request.json
    user_text = data.get('text', '').strip()
    lang = data.get('lang', 'English')

    if not user_text:
        return jsonify({"reply": "Please say or type something."})

    system_prompt = f"""
You are a strict, professional AI Finance & Investment Assistant.
You MUST reply ONLY in {lang} language.

STRICT RULES YOU MUST FOLLOW:

1. FINANCE-ONLY GUARDRAIL (NO NON-FINANCE ANSWERS):
   - You ONLY discuss topics related to personal finance, expense/income tracking, budgeting, savings, share market, stocks, mutual funds, SIP, banking, loans, taxes, and money management.
   - If the user asks about ANYTHING outside finance (e.g., movies, sports, politics, jokes, coding, general knowledge, casual non-finance chat), set "action": "none", "amount": 0, and reply strictly:
     * If {lang} is Bengali: "দুঃখিত, আমি শুধুমাত্র ফাইন্যান্স, টাকা-পয়সার হিসাব এবং ইনভেস্টমেন্ট সংক্রান্ত প্রশ্নের উত্তর দিই। অনুগ্রহ করে ফাইন্যান্স সম্পর্কিত প্রশ্ন করুন।"
     * If {lang} is Hindi: "क्षमा करें, मैं केवल फाइनेंस, हिसाब-किताब और निवेश से जुड़े सवालों के जवाब देता हूँ। कृपया फाइनेंस से संबंधित प्रश्न पूछें।"
     * If {lang} is English: "Sorry, I only answer questions related to finance, expense tracking, and investments. Please ask a finance-related question."

2. DO NOT ADD HYPOTHETICAL OR PLANNED AMOUNTS AS EXPENSES:
   - Set "action": "add" ONLY when the user clearly states a transaction HAS ALREADY HAPPENED (e.g., "I spent 500 on food", "৫০০ টাকা বাজার করলাম", "বেতন পেলাম ১০০০০ টাকা", "200 taka petrol bhorlam").
   - If the user is ASKING A QUESTION, SEEKING ADVICE, or PLANNING for the future (e.g., "আমি ৫০০ টাকা শেয়ার মার্কেটে ইনভেস্ট করতে চাই", "Where should I invest 500 rupees?", "৫০০ টাকা দিয়ে কী শেয়ার কিনব?", "আমি ১০০০ টাকা জমাতে চাই"), DO NOT record it as an expense or income! Set "action": "none", "amount": 0, and give helpful financial/investment guidance in "reply".

3. OUTPUT FORMAT (Strict JSON ONLY):
   Return ONLY a valid JSON object in this exact structure:
   {{
     "action": "add" or "none",
     "type": "expense" or "income",
     "amount": number (0 if action is "none"),
     "category": "Short category name in English (e.g., Food, Groceries, Salary, Investment)",
     "reply": "Your helpful response in {lang} (keep it concise, clear, and suitable for voice speaking, 1 to 3 sentences)"
   }}
"""

    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }

        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=15)
        res_json = response.json()
        ai_content = res_json['choices'][0]['message']['content']
        parsed = json.loads(ai_content)

        action = parsed.get("action", "none")
        tx_type = parsed.get("type", "expense")
        amount = float(parsed.get("amount", 0))
        category = parsed.get("category", "General")
        reply = parsed.get("reply", "Done.")

        # শুধুমাত্র সত্যিকারের খরচ বা ইনকাম হলেই ডাটাবেসে যোগ হবে
        if action == "add" and amount > 0:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tx_data = {
                "type": tx_type,
                "amount": amount,
                "category": category,
                "date": now_str
            }
            db.collection('users').document(user_email).collection('transactions').add(tx_data)

        daily, weekly, monthly = get_totals(user_email)
        return jsonify({
            "reply": reply,
            "daily": daily,
            "weekly": weekly,
            "monthly": monthly
        })

    except Exception as e:
        print("AI Chat Error:", e)
        return jsonify({"reply": "Sorry, I couldn't process that right now."})
if __name__ == '__main__':
    app.run(debug=True)
