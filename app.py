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
        
    email = (request.form.get('email') or '').strip().lower()
    password = request.form.get('password') or ''
    selected_role = (request.form.get('role') or '').strip().lower()

    if not selected_role:
        flash("Please select your category.")
        return redirect(url_for('home'))

    user_doc = db.collection("users").document(email).get()
    if user_doc.exists:
        user_data = user_doc.to_dict()
        if user_data.get("password") == hash_pass(password):
            saved_role = user_data.get("role")
            
            # যদি আগে থেকেই ক্যাটাগরি সেভ থাকে এবং ইউজার অন্য ক্যাটাগরি সিলেক্ট করে তবে লগইন ব্লক করবে
            if saved_role and saved_role != selected_role:
                role_labels = {
                    "business": "Business",
                    "student": "Student",
                    "job": "Job Person",
                    "worker": "Any Worker"
                }
                correct_name = role_labels.get(saved_role, saved_role.capitalize())
                flash(f"This email is registered under '{correct_name}' category. Please select '{correct_name}' to login.")
                return redirect(url_for('home'))
            
            # পুরনো অ্যাকাউন্টে যদি আগে role না থেকে থাকে, তবে প্রথমবার লগইনে সেটি লক করে দেবে
            if not saved_role:
                db.collection("users").document(email).update({"role": selected_role})
                saved_role = selected_role

            session.permanent = True
            session['username'] = email
            session['role'] = saved_role
            return redirect(url_for('dashboard'))

    flash("Invalid email or password.")
    return redirect(url_for('home'))

@app.route('/register', methods=['POST'])
def register():
    email = (request.form.get('email') or '').strip().lower()
    password = request.form.get('password') or ''
    selected_role = (request.form.get('role') or '').strip().lower()

    if not selected_role:
        flash("Please select a category to register.")
        return redirect(url_for('home'))

    if db.collection("users").document(email).get().exists:
        flash("Account already exists with this email! Please login.")
        return redirect(url_for('home'))
    else:
        db.collection("users").document(email).set({
            "password": hash_pass(password),
            "role": selected_role
        })
        session.permanent = True
        session['username'] = email
        session['role'] = selected_role
        return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('home'))
    daily_total, weekly_total, monthly_total = get_totals(session['username'])
    user_role = session.get('role', 'business')
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
        non_finance_msg = "দুঃখিত, আমি শুধুমাত্র ফাইন্যান্স, টাকা-পয়সার হিসাব এবং ইনভেস্টমেন্ট সংক্রান্ত প্রশ্নের উত্তর দিই। অনুগ্রহ করে ফাইন্যান্স সম্পর্কিত প্রশ্ন করুন।"
    elif ai_lang == 'Hindi':
        lang_instruction = "You MUST write 'reply_message' and 'category' strictly in Hindi Devanagari script (हिंदी में)."
        non_finance_msg = "क्षमा करें, मैं केवल फाइनेंस, हिसाब-किताब और निवेश से जुड़े सवालों के जवाब देता हूँ। कृपया फाइनेंस से संबंधित प्रश्न पूछें।"
    else:
        lang_instruction = "You MUST write 'reply_message' and 'category' strictly in English."
        non_finance_msg = "Sorry, I only answer questions related to finance, expense tracking, and investments. Please ask a finance-related question."
    
    prompt = f"""
    User message: "{user_input}"
    User Category/Role: {user_role}
    Selected Language: {ai_lang}
    
    STRICT RULES YOU MUST FOLLOW:
    1. FINANCE-ONLY GUARDRAIL:
       - You ONLY discuss personal/business finance, expense/income tracking, EMI, GST, profit/loss, budgeting, savings, share market, stocks, mutual funds, SIP, daily wages, and money management (plus basic greetings like Hi/Hello/হাই/হ্যালো).
       - If the user asks about ANYTHING outside finance (e.g., movies, sports, politics, jokes, coding, general knowledge, etc.), you MUST keep "transactions": [] and set "reply_message" strictly to: "{non_finance_msg}"

    2. DO NOT ADD HYPOTHETICAL OR PLANNED AMOUNTS AS TRANSACTIONS:
       - Add an item to the "transactions" array ONLY when the user clearly states that an expense or income HAS ALREADY HAPPENED (e.g., "৫০০ টাকা মাছ কিনলাম", "I spent 200 on food", "বেতন পেলাম ১০০০০ টাকা").
       - If the user is ASKING A QUESTION, CALCULATING EMI/PROFIT/GST, SEEKING ADVICE, or PLANNING TO INVEST in the future (e.g., "আমি ৫০০ টাকা শেয়ার মার্কেটে ইনভেস্ট করতে চাই", "Where should I invest 500 taka?"), DO NOT add it to "transactions"! Keep "transactions": [] and give helpful financial calculation/advice in "reply_message".

    3. TRANSACTION EXTRACTION FORMAT (only for completed transactions):
       Each object in "transactions" MUST have:
       - "category": Item/expense name written strictly in {ai_lang}
       - "category_en": Item/expense name in English (e.g., "Fish")
       - "category_bn": Item/expense name in Bengali script (e.g., "মাছ")
       - "category_hi": Item/expense name in Hindi script (e.g., "मछली")
       - "amount": Numeric value only
       - "type": strictly "income" (if money received/salary/earned) OR "expense" (if money spent/bought/paid).
       If no real completed transaction is mentioned, keep "transactions" as [].

    4. {lang_instruction}
    5. Make "reply_message" a friendly, natural conversational reply in {ai_lang} and end with a short finance-related follow-up question.
    
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
                    "content": f"You are a strict live conversational AI Finance & Investment Agent. {lang_instruction} You never answer non-finance questions and never record planned/hypothetical investments as completed expenses. Output pure JSON only."
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
                            "role": user_role,
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
