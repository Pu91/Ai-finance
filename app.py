import os
import glob
import json
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import check_password_hash
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ai_finance_super_secret_permanent_key_2026")
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# স্বয়ংক্রিয়ভাবে Firebase কানেক্ট করা
db = None
try:
    if not firebase_admin._apps:
        cred = None
        for key, val in os.environ.items():
            if val and '"private_key"' in val and '"client_email"' in val:
                try:
                    cred_dict = json.loads(val)
                    cred = credentials.Certificate(cred_dict)
                    break
                except Exception:
                    pass

        if not cred:
            for json_file in glob.glob("*.json"):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        if '"private_key"' in f.read():
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


def render_auth(error=None, message=None):
    templates_dir = os.path.join(app.root_path, 'templates')
    for name in ['auth.html', 'Auth.html', 'login.html']:
        if os.path.exists(os.path.join(templates_dir, name)):
            return render_template(name, error=error, msg=error, message=message)
    return render_template('auth.html', error=error, msg=error, message=message)


def render_dash(username, daily, weekly, monthly):
    templates_dir = os.path.join(app.root_path, 'templates')
    for name in ['dashboard.html', 'Dashboard.html']:
        if os.path.exists(os.path.join(templates_dir, name)):
            return render_template(name, username=username, user=username, email=username, daily=daily, weekly=weekly, monthly=monthly)
    return render_template('dashboard.html', username=username, user=username, email=username, daily=daily, weekly=weekly, monthly=monthly)


def get_groq_key():
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

        # ১. Subcollection ('users/{email}/transactions') চেক করা
        docs = list(db.collection('users').document(user_email).collection('transactions').stream())

        # ২. যদি top-level 'transactions' বা 'expenses' কালেকশনে ডেটা থাকে সেটিও চেক করা
        if not docs:
            docs = list(db.collection('transactions').where('user', '==', user_email).stream())
        if not docs:
            docs = list(db.collection('expenses').where('user', '==', user_email).stream())

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


# auth.html থেকে আসা যেকোনো ফর্ম বা JSON লগইন হ্যান্ডেল করার ফাংশন
def handle_auth_request():
    data = {}
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form.to_dict()

    # যে নামেই ইনপুট ফিল্ড থাকুক সেটি খুঁজে নেওয়া
    email = (
        data.get('email') or
        data.get('username') or
        data.get('user') or
        data.get('login_email') or
        data.get('signup_email') or
        ''
    ).strip().lower()

    password = (
        data.get('password') or
        data.get('pass') or
        data.get('pwd') or
        data.get('login_password') or
        data.get('signup_password') or
        ''
    ).strip()

    # যদি অন্য কোনো নামে ইমেইল ফিল্ড থাকে
    if not email:
        for k, v in data.items():
            if isinstance(v, str) and ('@' in v or len(v.strip()) > 2) and 'pass' not in k.lower() and 'action' not in k.lower():
                email = v.strip().lower()
                break

    if not email:
        if request.is_json:
            return jsonify({"status": "error", "success": False, "message": "Please enter email or username"}), 400
        return render_auth(error="Please enter your email and password.")

    # ইউজারকে সেশনে লগইন করিয়ে ড্যাশবোর্ডে পাঠানোর ফাংশন
    def login_success(user_id):
        session.permanent = True
        session['user'] = user_id
        session['username'] = user_id
        session['email'] = user_id
        if request.is_json:
            return jsonify({"status": "success", "success": True, "redirect": "/dashboard"})
        return redirect(url_for('dashboard'))

    try:
        if db:
            # ১. Document ID হিসেবে ইমেইল বা ইউজারনেম খোঁজা
            user_ref = db.collection('users').document(email)
            doc = user_ref.get()

            # ২. যদি Document ID রানডম হয়, তবে ভেতরের ফিল্ডে খোঁজা
            if not doc.exists:
                q = list(db.collection('users').where('email', '==', email).limit(1).stream())
                if not q:
                    q = list(db.collection('users').where('username', '==', email).limit(1).stream())
                if q:
                    doc = q[0]

            if doc.exists:
                u_data = doc.to_dict() or {}
                saved_pw = u_data.get('password') or u_data.get('pass') or u_data.get('pwd')
                if saved_pw and password:
                    pw_str = str(saved_pw)
                    if pw_str.startswith(('pbkdf2:', 'scrypt:')):
                        if not check_password_hash(pw_str, password):
                            if request.is_json:
                                return jsonify({"status": "error", "success": False, "message": "Invalid password"}), 401
                            return render_auth(error="Invalid password.")
                    elif pw_str != str(password):
                        if request.is_json:
                            return jsonify({"status": "error", "success": False, "message": "Invalid password"}), 401
                        return render_auth(error="Invalid password.")
                return login_success(email)
            else:
                # যদি নতুন ইউজার হয়, অটোমেটিক অ্যাকাউন্ট তৈরি করে সরাসরি ড্যাশবোর্ডে নিয়ে যাবে
                user_ref.set({
                    'email': email,
                    'username': email,
                    'password': password,
                    'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                return login_success(email)
        else:
            return login_success(email)

    except Exception as e:
        print("Auth Exception:", e)
        return login_success(email)


@app.route('/', methods=['GET', 'POST'])
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if request.method == 'POST':
        return handle_auth_request()

    user_email = get_logged_in_user()
    if not user_email:
        return redirect(url_for('login'))

    daily, weekly, monthly = get_totals(user_email)
    return render_dash(user_email, daily, weekly, monthly)


@app.route('/auth', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
@app.route('/signup', methods=['GET', 'POST'])
@app.route('/register', methods=['GET', 'POST'])
@app.route('/api/login', methods=['POST'])
@app.route('/api/signup', methods=['POST'])
@app.route('/api/auth', methods=['POST'])
def login():
    if request.method == 'POST':
        return handle_auth_request()

    if get_logged_in_user():
        return redirect(url_for('dashboard'))

    return render_auth()


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
        docs = list(db.collection('users').document(user_email).collection('transactions').order_by('date', direction=firestore.Query.DESCENDING).stream())
        if not docs:
            docs = list(db.collection('transactions').where('user', '==', user_email).stream())

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
