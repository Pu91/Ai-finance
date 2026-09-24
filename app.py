from flask import Flask, render_template, request, session, redirect, url_for, flash
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai
import datetime
import os
import hashlib

app = Flask(__name__)
app.secret_key = "super_secret_finance_key" # সেশনের জন্য সিক্রেট কি

# --- API ও ডেটাবেস কানেকশন ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("firebase-key.json")
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print("Firebase Error:", e)

db = firestore.client()

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- রাউটস (Routes) ---

@app.route('/')
def home():
    # ইউজার লগিন থাকলে ড্যাশবোর্ড দেখাবে, না থাকলে লগিন পেজ
    if 'username' in session:
        # ইউজারের আগের হিসাবগুলো ডেটাবেস থেকে আনা
        from google.cloud.firestore_v1.base_query import FieldFilter
        expenses_ref = db.collection("expenses").where(filter=FieldFilter("username", "==", session['username'])).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).stream()
        
        expenses = []
        for exp in expenses_ref:
            expenses.append(exp.to_dict())
            
        return render_template('index.html', logged_in=True, username=session['username'], expenses=expenses)
    
    return render_template('index.html', logged_in=False)

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    user_ref = db.collection("users").document(username).get()
    if user_ref.exists:
        if user_ref.to_dict().get("password") == hash_password(password):
            session['username'] = username
            return redirect(url_for('home'))
        else:
            flash("❌ পাসওয়ার্ড ভুল হয়েছে!")
    else:
        flash("❌ ইউজারনেম পাওয়া যায়নি!")
    return redirect(url_for('home'))

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')
    
    user_ref = db.collection("users").document(username).get()
    if user_ref.exists:
        flash("⚠️ এই নাম আগে থেকেই আছে!")
    else:
        db.collection("users").document(username).set({
            "password": hash_password(password),
            "created_at": firestore.SERVER_TIMESTAMP
        })
        session['username'] = username # ডিরেক্ট লগিন
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

@app.route('/add_expense', methods=['POST'])
def add_expense():
    if 'username' not in session:
        return redirect(url_for('home'))
        
    user_input = request.form.get('expense_text')
    if user_input and GEMINI_API_KEY:
        prompt = f'তুমি হিসাবরক্ষক। মেসেজ থেকে খরচের খাত ও পরিমাণ বের করো। মেসেজ: "{user_input}"। শুধু কমা দিয়ে ক্যাটাগরি ও টাকা লিখবে। যেমন: চা, ২০'
        try:
            response = model.generate_content(prompt)
            ai_output = response.text.strip().split(',')
            
            if len(ai_output) == 2:
                cat = ai_output[0].strip()
                amt = ai_output[1].strip()
                
                db.collection("expenses").document().set({
                    "username": session['username'],
                    "category": cat,
                    "amount": amt,
                    "date": datetime.datetime.now().strftime("%d %b %Y, %I:%M %p"),
                    "timestamp": firestore.SERVER_TIMESTAMP
                })
            else:
                flash("⚠️ AI হিসাবটা বুঝতে পারেনি।")
        except Exception as e:
            flash(f"⚠️ API Error: {e}")
            
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
