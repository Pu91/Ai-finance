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
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=30)

# Groq API Setup
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return redirect(url_for('home'))
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    selected_role = request.form.get('role', '').strip()

    user_ref = db.collection("users").document(email)
    user = user_ref.get()
    if user.exists and user.to_dict().get("password") == hash_pass(password):
        session.permanent = True
        session['username'] = email
        # ইউজার লগইনের সময় যে ড্যাশবোর্ড সিলেক্ট করবে সেটি সেট হবে
        role = selected_role or user.to_dict().get("role", "business")
        session['role'] = role
        user_ref.update({"role": role})
        return redirect(url_for('dashboard'))

    flash("Invalid email or password.")
    return redirect(url_for('home'))

@app.route('/register', methods=['POST'])
def register():
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    role = request.form.get('role', 'business').strip()

    if db.collection("users").document(email).get().exists:
        flash("Account already exists with this email! Please Login.")
        return redirect(url_for('home'))
    else:
        db.collection("users").document(email).set({
            "password": hash_pass(password),
            "role": role
        })
        session.permanent = True
        session['username'] = email
        session['role'] = role
        return redirect(url_for('dashboard'))

@app.route('/switch_role/<new_role>')
def switch_role(new_role):
    if 'username' not in session:
        return redirect(url_for('home'))
    if new_role in ['business', 'student', 'job', 'worker']:
        session['role'] = new_role
        try:
            db.collection("users").document(session['username']).update({"role": new_role})
        except Exception:
            pass
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('home'))
    user_role = session.get('role')
    if not user_role:
        user_doc = db.collection("users").document(session['username']).get()
        user_role = user_doc.to_dict().get("role", "business") if user_doc.exists else "business"
        session['role'] = user_role

    daily_total, weekly_total, monthly_total = get_totals(session['username'])
    return render_template(
        'dashboard.html',
        username=session['username'],
        role=user_role,
        daily=daily_total,
        weekly=weekly_total,
        monthly=monthly_total
    )

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
        return jsonify({"reply": "Please login first."}), 401
    
    user_input = request.json.get('text', '')
    ai_lang = request.json.get('lang', 'English')
    user_role = session.get('role', 'business')
    
    if ai_lang == 'Bengali':
        lang_instruction = "You MUST write 'reply_message' and 'category' strictly in Bengali script (বাংলা হরফে)."
        non_finance_msg = "দুঃখিত, আমি শুধুমাত্র ফাইন্যান্স, টাকা-পয়সার হিসাব, EMI, ব্যবসা এবং ইনভেস্টমেন্ট সংক্রান্ত প্রশ্নের উত্তর দিই।"
    elif ai_lang == 'Hindi':
        lang_instruction = "You MUST write 'reply_message' and 'category' strictly in Hindi Devanagari script (हिंदी में)."
        non_finance_msg = "क्षमा करें, मैं केवल फाइनेंस, हिसाब-किताब, EMI और निवेश से जुड़े सवालों के जवाब देता हूँ।"
    else:
        lang_instruction = "You MUST write 'reply_message' and 'category' strictly in English."
        non_finance_msg = "Sorry, I only answer questions related to finance, EMI, business calculations, and expense tracking."
    
    prompt = f"""
    User message: "{user_input}"
    User Profession/Role: {user_role}
    Selected Language: {ai_lang}
    
    STRICT RULES YOU MUST FOLLOW:
    1. FINANCE & CALCULATION GUARDRAIL:
       - You ONLY answer topics related to personal finance, expense/income tracking, EMI calculation, interest calculation, business profit/loss, GST, discounts, student bill splitting, salary planning, SIP/mutual funds, daily wages (হাজিরা/মজুরি), and money management.
       - If the user asks about ANYTHING outside finance/math calculations (e.g., movies, sports, politics, jokes, general knowledge), keep "transactions": [] and set "reply_message" strictly to: "{non_finance_msg}"

    2. SMART CALCULATIONS vs REAL EXPENSES:
       - If the user asks to CALCULATE something (e.g., Loan EMI, interest, business profit, GST, discount, wage math, mess split, or investment plans like "আমি ৫০০ টাকা শেয়ার মার্কেটে ইনভেস্ট করতে চাই" or "১ লাখ টাকার ১০% সুদে ২ বছরের EMI কত?"), DO NOT add it to "transactions"! Keep "transactions": [] and solve the exact calculation clearly in "reply_message".
       - Add an item to "transactions" ONLY when the user clearly states an expense or income HAS ALREADY HAPPENED (e.g., "৫০০ টাকা মাছ কিনলাম", "আজকে ৬০০ টাকা মজুরি পেলাম", "দোকানে ২০০০ টাকা মাল কিনলাম").

    3. TRANSACTION EXTRACTION FORMAT (only for completed transactions):
       Each object in "transactions" MUST have:
       - "category": Item/expense name written strictly in {ai_lang}
       - "category_en": Item/expense name in English
       - "category_bn": Item/expense name in Bengali script
       - "category_hi": Item/expense name in Hindi script
       - "amount": Numeric value only
       - "type": strictly "income" OR "expense".

    4. {lang_instruction}
    
    Return ONLY valid JSON in this exact format:
    {{
      "transactions": [],
      "reply_message": "Your accurate financial answer or confirmation strictly in {ai_lang}"
    }}
    """
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": f"You are a live conversational AI Finance & Smart Calculator Agent for a {user_role}. {lang_instruction} Output pure JSON only."
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
                    if numeric_amt > 0:
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
