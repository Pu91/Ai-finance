import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai
import datetime
import os

# Render-এর Environment Variable থেকে Gemini API Key নেবে (সুরক্ষার জন্য)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.error("⚠️ Gemini API Key পাওয়া যায়নি!")

# Render-এর Secret File থেকে Firebase Key নেবে
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("firebase-key.json") 
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"⚠️ Firebase কানেক্ট করা যাচ্ছে না: {e}")

db = firestore.client()

# ওয়েব অ্যাপের ডিজাইন
st.title("🎙️ এআই হিসাবরক্ষক")
st.write("আপনার খরচের কথা নিচে লিখুন বা মোবাইলের কীবোর্ডের ভয়েস-টাইপিং দিয়ে বলুন:")

user_input = st.text_input("যেমন: আজকে ২০০ টাকার পেট্রোল ভরলাম")

if st.button("হিসাব সেভ করুন"):
    if user_input and GEMINI_API_KEY:
        st.info("AI আপনার হিসাব প্রসেস করছে...")
        
        prompt = f"""
        তুমি একজন স্মার্ট হিসাবরক্ষক। ইউজারের এই মেসেজ থেকে খরচের খাত (Category) এবং টাকার পরিমাণ (Amount) বের করো।
        মেসেজ: "{user_input}"
        শুধু কমা (,) দিয়ে ক্যাটাগরি এবং টাকার অংক লিখবে। অন্য কোনো শব্দ লিখবে না। যেমন: যাতায়াত, ২০০
        """
        
        try:
            response = model.generate_content(prompt)
            ai_output = response.text.strip().split(',')
            
            if len(ai_output) == 2:
                category = ai_output[0].strip()
                amount = ai_output[1].strip()
                
                db.collection("expenses").document().set({
                    "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "text_input": user_input,
                    "category": category,
                    "amount": amount
                })
                st.success(f"✅ সেভ হয়েছে! খাত: {category} | টাকা: {amount}")
            else:
                st.warning("AI হিসাবটা ঠিক বুঝতে পারেনি। আবার চেষ্টা করুন।")
        except Exception as e:
            st.error(f"কোনো সমস্যা হয়েছে: {e}")
    else:
        st.warning("দয়া করে কিছু লিখুন!")

st.subheader("আপনার সর্বশেষ খরচ:")
try:
    expenses = db.collection("expenses").order_by("date", direction=firestore.Query.DESCENDING).limit(5).stream()
    for exp in expenses:
        data = exp.to_dict()
        st.write(f"📅 {data.get('date', '')} | 🛍️ {data.get('category', '')}: {data.get('amount', '')} টাকা")
except:
    st.write("এখনো কোনো হিসাব যোগ করা হয়নি বা ডেটাবেস কানেক্ট হয়নি।")
