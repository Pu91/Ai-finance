import os
import glob
import json
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ai_finance_super_secret_permanent_key_2026")
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# স্বয়ংক্রিয়ভাবে যেকোনো Environment Variable বা JSON ফাইল থেকে Firebase কানেক্ট করার ফাংশন
db = None
try:
    if not firebase_admin._apps:
        cred = None
        # ১. Render Environment Variables চেক করা
        for key, val in os.environ.items():
            if val and '"private_key"' in val and '"client_email"' in val:
                try:
                    cred_dict = json.loads(val)
                    cred = credentials.Certificate(cred_dict)
                    break
                except Exception:
                    pass

        # ২. প্রজেক্ট ফোল্ডারের ভেতরে যেকোনো .json ফাইল চেক করা
        if not cred:
            for json_file in glob.glob("*.json"):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        content = f.read()
                        if '"private_key"' in content:
                            cred = credentials.Certificate(json_file)
                            break
                except Exception:
                    pass

        if cred:
            firebase_admin.initialize_app(cred)
        else:
            firebase_admin.initialize_app()

    db = firestore.client()
except Exception as e:
    print("Firebase Initialization Warning:", e)


def get_groq_key():
    # যে নামেই Groq API Key সেভ থাকুক সেটি খুঁজে নেবে
    for k, v in os.environ.items():
        if "GROQ" in k.upper() or (v and v.startswith("gsk_")):
            return v.strip()
    return ""


def get_logged_in_user():
    for key in ['user', 'username', 'email', 'user_email']:
        if session.get(key):
            return session.get(key)
    return None


def get_totals(user_email):
    daily, weekly, monthly = 0.0, 0.0, 0.0
    if not db or not user_email:
        return daily, weekly, monthly

    try:
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        week_ago = now - timedelta(days=7)
        month_prefix = now.strftime("%Y-%m")

        docs = db.collection('users').document(user_email).collection('transactions').stream()
        for doc in docs:
            d = doc.to_dict()
            if d.get('type', 'expense') == 'expense':
                amt = float(d.get('amount', 0))
                date_str = str(d.get('date', ''))

                if date_str.startswith(today_str):
                    daily += amt
                if date_str.startswith(month_prefix):
                    monthly += amt
                try:
                    tx_date = datetime.strptime(date_str[:10], "%Y-%m-%d")
                    if tx_date >= week_ago.replace(hour=0, minute=0, second=0, microsecond=0):
                        weekly += amt
                except Exception:
                    pass
    except Exception as e:
        print("Error calculating totals:", e)

    return round(daily, 2), round(weekly, 2), round(monthly, 2)


@app.route('/')
@app.route('/dashboard')
def dashboard():
    user_email = get_logged_in_user()
    if not user_email:
        return redirect(url_for('login'))

    daily, weekly, monthly = get_totals(user_email)
    return render_template('dashboard.html', username=user_email, daily=daily, weekly=weekly, monthly=monthly)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or request.form.get('username') or '').strip().lower()
        password = (request.form.get('password') or '').strip()

        if not email or not password:
            return render_template('login.html', error="Please enter email and password.")

        try:
            user_ref = db.collection('users').document(email).get()
            if user_ref.exists:
                user_data = user_ref.to_dict()
                if str(user_data.get('password')) == str(password):
                    session.permanent = True
                    session['user'] = email
                    session['username'] = email
                    session['email'] = email
                    return redirect(url_for('dashboard'))
                else:
                    return render_template('login.html', error="Invalid password.")
            else:
                return render_template('login.html', error="Account not found. Please Sign Up.")
        except Exception as e:
            print("Login error:", e)
            return render_template('login.html', error="Login failed. Please try again.")

    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
@app.route('/register', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = (request.form.get('email') or request.form.get('username') or '').strip().lower()
        password = (request.form.get('password') or '').strip()

        if not email or not password:
            return render_template('signup.html', error="All fields are required.")

        try:
            user_ref = db.collection('users').document(email)
            if user_ref.get().exists:
                return render_template('signup.html', error="Account already exists! Please login.")

            user_ref.set({
                'email': email,
                'password': password,
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            session.permanent = True
            session['user'] = email
            session['username'] = email
            session['email'] = email
            return redirect(url_for('dashboard'))
        except Exception as e:
            print("Signup error:", e)
            return render_template('signup.html', error="Error creating account.")

    return render_template('signup.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/details/<period>')
def details(period):
    user_email = get_logged_in_user()
    if not user_email:
        return redirect(url_for('login'))

    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    week_ago = now - timedelta(days=7)
    month_prefix = now.strftime("%Y-%m")

    transactions = []
    try:
        docs = db.collection('users').document(user_email).collection('transactions').order_by('date', direction=firestore.Query.DESCENDING).stream()
        for doc in docs:
            d = doc.to_dict()
            date_str = str(d.get('date', ''))
            include = False

            if period == 'daily' and date_str.startswith(today_str):
                include = True
            elif period == 'monthly' and date_str.startswith(month_prefix):
                include = True
            elif period == 'weekly':
                try:
                    tx_date = datetime.strptime(date_str[:10], "%Y-%m-%d")
                    if tx_date >= week_ago.replace(hour=0, minute=0, second=0, microsecond=0):
                        include = True
                except Exception:
                    pass

            if include:
                transactions.append({
                    'id': doc.id,
                    'category': d.get('category', 'General'),
                    'amount': float(d.get('amount', 0)),
                    'type': d.get('type', 'expense'),
                    'date': date_str
                })
    except Exception as e:
        print("Details error:", e)

    return render_template('details.html', period=period.capitalize(), transactions=transactions, username=user_email)


@app.route('/api/chat', methods=['POST'])
def ai_chat():
    user_email = get_logged_in_user()
    if not user_email:
        return jsonify({"reply": "অনুগ্রহ করে মেনু থেকে একবার লগআউট করে আবার লগইন করুন।"}), 401

    data = request.json or {}
    user_text = data.get('text', '').strip()
    lang = data.get('lang', 'English')

    if not user_text:
        return jsonify({"reply": "Please say or type something."})

    system_prompt = f"""
You are a smart, strict, and polite AI Finance & Investment Assistant.
You MUST reply ONLY in {lang} language.

STRICT RULES YOU MUST FOLLOW:

1. GREETINGS (Hi / Hello / হাই / হ্যালো / নমস্কার):
   - If the user greets you, set "action": "none", "amount": 0, and warmly greet them back in {lang} as their AI Finance Assistant.

2. FINANCE-ONLY GUARDRAIL (REJECT NON-FINANCE QUESTIONS):
   - You ONLY answer questions related to personal finance, expense/income tracking, budgeting, savings, share market, stocks, mutual funds, SIP, gold, banking, loans, taxes, business, and money management.
   - If the user asks about ANYTHING outside finance (sports, movies, politics, jokes, general knowledge, etc.), set "action": "none", "amount": 0, and strictly reply:
     * If {lang} is Bengali: "দুঃখিত, আমি শুধুমাত্র ফাইন্যান্স, টাকা-পয়সার হিসাব এবং ইনভেস্টমেন্ট সংক্রান্ত প্রশ্নের উত্তর দিই। অনুগ্রহ করে ফাইন্যান্স সম্পর্কিত প্রশ্ন করুন।"
     * If {lang} is Hindi: "क्षमा करें, मैं केवल फाइनेंस, हिसाब-किताब और निवेश से जुड़े सवालों के जवाब देता हूँ। कृपया फाइनेंस से संबंधित प्रश्न पूछें।"
     * If {lang} is English: "Sorry, I only answer questions related to finance, expense tracking, and investments. Please ask a finance-related question."

3. DO NOT ADD QUESTIONS OR FUTURE PLANS AS EXPENSES:
   - Set "action": "add" ONLY when the user clearly states a real transaction HAS ALREADY HAPPENED (e.g., "আমি ৫০০ টাকা বাজার করলাম", "I spent 200 on food", "বেতন পেলাম ১০০০০ টাকা").
   - If the user is ASKING FOR ADVICE, PLANNING TO INVEST, or asking a hypothetical question (e.g., "আমি ৫০০ টাকা শেয়ার মার্কেটে ইনভেস্ট করতে চাই", "৫০০ টাকা কোথায় ইনভেস্ট করব?"), DO NOT add it to expenses or income! Set "action": "none" and "amount": 0, and provide helpful investment advice in "reply".

4. JSON OUTPUT FORMAT:
   Respond ONLY with a valid JSON object:
   {{
     "action": "add" or "none",
     "type": "expense" or "income",
     "amount": number (0 if action is "none"),
     "category": "Short category name in English (e.g., Food, Groceries, Transport, Salary, Investment)",
     "reply": "Your clear, natural response in {lang} (1 to 3 sentences)"
   }}
"""

    try:
        api_key = get_groq_key()
        headers = {
            "Authorization": f"Bearer {api_key}",
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

        if action == "add" and amount > 0 and db:
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
        return jsonify({"reply": "দুঃখিত, এই মুহূর্তে উত্তর দিতে সমস্যা হচ্ছে। অনুগ্রহ করে আবার চেষ্টা করুন।"})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
