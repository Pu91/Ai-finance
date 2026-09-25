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

# রিয়েল-টাইমে মোট খরচ হিসাব করার ফাংশন
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
    total = 0
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
            filtered_exp.append(data)
            try:
                total += float(data.get("amount", 0))
            except (ValueError, TypeError):
                pass

    # নতুন খরচগুলো সবার উপরে দেখানোর জন্য সর্টিং
    filtered_exp.sort(key=lambda x: x['_sort_time'], reverse=True)
            
    return render_template('details.html', period=period.capitalize(), expenses=filtered_exp, total=total)

@app.route('/api/chat', methods=['POST'])
def api_chat():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user_input = request.json.get('text')
    ai_lang = request.json.get('lang', 'English') 
    
    prompt = f"""
    The user is talking to you: "{user_input}"
    
    Instructions:
    1. If the user mentions any expenses, extract them into the "expenses" list with "category" and numeric "amount". If it is general conversation without any expense, keep "expenses" as an empty list [].
    2. Write a natural, friendly conversational reply in {ai_lang} language inside "reply_message". Talk like a smart human finance assistant. Keep it short and clear so it sounds great on voice output.
    
    Return ONLY a valid JSON object with these two keys:
    {{
      "expenses": [{{"category": "Fish", "amount": 500}}],
      "reply_message": "Your conversational response in {ai_lang}"
    }}
    """
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a smart, friendly conversational AI Finance Agent. You always output pure JSON."
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
        
        expenses = ai_data.get("expenses", [])
        reply = ai_data.get("reply_message", "Processed successfully.")
        
        for item in expenses:
            cat = item.get("category")
            amt = item.get("amount")
            if cat and amt is not None:
                try:
                    numeric_amt = float(amt)
                    db.collection("expenses").document().set({
                        "username": session['username'],
                        "category": cat,
                        "amount": numeric_amt,
                        "date_str": datetime.datetime.now().strftime("%d %b %Y, %I:%M %p"),
                        "timestamp": firestore.SERVER_TIMESTAMP
                    })
                except (ValueError, TypeError):
                    pass
                    
        # পেজ রিলোড না করেই ড্যাশবোর্ডের কার্ড আপডেট করার জন্য নতুন টোটাল পাঠানো হচ্ছে
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
