from flask import Flask, render_template, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai
import datetime
import os

app = Flask(__name__)

# API ও ডেটাবেস কানেকশন
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-key.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

@app.route('/')
def home():
    return render_template('index.html') # এটি আপনার HTML ফাইল লোড করবে

@app.route('/api/save_expense', methods=['POST'])
def save_expense():
    data = request.json
    user_input = data.get("text", "")
    
    if user_input and GEMINI_API_KEY:
        prompt = f'তুমি একজন স্মার্ট হিসাবরক্ষক। মেসেজ থেকে খরচের খাত এবং টাকার পরিমাণ বের করো। মেসেজ: "{user_input}"। শুধু কমা দিয়ে ক্যাটাগরি এবং টাকার অংক লিখবে। যেমন: বাজার, ৩০০'
        try:
            response = model.generate_content(prompt)
            ai_output = response.text.strip().split(',')
            
            if len(ai_output) == 2:
                category = ai_output[0].strip()
                amount = ai_output[1].strip()
                
                exp_data = {
                    "date": datetime.datetime.now().strftime("%d %b %Y, %I:%M %p"),
                    "text_input": user_input,
                    "category": category,
                    "amount": amount,
                    "timestamp": firestore.SERVER_TIMESTAMP
                }
                db.collection("expenses").document().set(exp_data)
                return jsonify({"status": "success", "data": exp_data})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
            
    return jsonify({"status": "error", "message": "Input missing or AI failed"})

@app.route('/api/get_expenses', methods=['GET'])
def get_expenses():
    expenses = db.collection("expenses").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).stream()
    exp_list = []
    for exp in expenses:
        data = exp.to_dict()
        data.pop('timestamp', None) # JSON এ timestamp পাঠানো যায় না
        exp_list.append(data)
    return jsonify(exp_list)

if __name__ == '__main__':
    app.run(debug=True)
