# ✅ Full Integration: Data Science Book Library with All Features

import streamlit as st
import base64
import bcrypt
import urllib.parse
from pymongo import MongoClient
from datetime import datetime, timedelta
import pandas as pd
import smtplib
from email.message import EmailMessage
import random
import fitz  # PyMuPDF for PDF previews
import plotly.express as px

# --- Secrets and MongoDB Setup ---
db_username = st.secrets["mongodb"]["username"]
db_password = st.secrets["mongodb"]["password"]
db_cluster = st.secrets["mongodb"]["cluster"]
db_name = st.secrets["mongodb"]["appname"]
admin_user = st.secrets["mongodb"]["admin_user"]
admin_pass = st.secrets["mongodb"]["admin_pass"]

SMTP_EMAIL = st.secrets["smtp"]["email"]
SMTP_PASSWORD = st.secrets["smtp"]["password"]
SMTP_SERVER = st.secrets["smtp"]["server"]
SMTP_PORT = st.secrets["smtp"]["port"]

client = MongoClient(f"mongodb+srv://{db_username}:{db_password}@{db_cluster}/?retryWrites=true&w=majority&appName={db_name}")
db = client["library"]
books_col = db["books"]
users_col = db["users"]
logs_col = db["logs"]
otp_col = db["otp_collection"]
fav_col = db["favorites"]

# --- Theme Toggle ---
def set_theme():
    theme = st.radio("Select Theme", ["Light", "Dark"], horizontal=True)
    if theme == "Dark":
        st.markdown("""
            <style>
            body {
                background-color: #0E1117;
                color: white;
            }
            </style>
        """, unsafe_allow_html=True)

# --- Email Utility ---
def send_email(to, subject, content):
    msg = EmailMessage()
    msg.set_content(content)
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = to
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)

# --- Registration with Email Verification ---
def register_user():
    st.subheader("📝 Register")
    username = st.text_input("Choose a username", key="reg_username")
    password = st.text_input("Choose a password", type="password", key="reg_password")
    email = st.text_input("Enter your email (required for verification)", key="reg_email")

    if st.button("Register"):
        if users_col.find_one({"username": username}):
            st.error("❌ Username already exists!")
        else:
            otp = str(random.randint(100000, 999999))
            send_email(email, "Verify your Email", f"Your verification code is: {otp}")
            entered = st.text_input("Enter the OTP sent to your email")
            if entered == otp:
                hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
                users_col.insert_one({
                    "username": username,
                    "password": hashed_pw,
                    "email": email,
                    "verified": True,
                    "created_at": datetime.utcnow()
                })
                st.success("✅ Registered and Verified! You can now log in.")
            else:
                st.warning("⚠️ Incorrect OTP")

# --- Login ---
def login_user():
    st.subheader("🔐 Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Login"):
        if username == admin_user and password == admin_pass:
            st.session_state["user"] = "admin"
            st.success("🛡️ Logged in as Admin")
        else:
            user = users_col.find_one({"username": username})
            if user and user.get("verified") and bcrypt.checkpw(password.encode(), user["password"]):
                st.session_state["user"] = username
                st.success(f"✅ Welcome {username}")
            else:
                st.error("❌ Invalid or unverified credentials!")

# --- Upload Book with Email Notifications ---
def upload_book():
    st.subheader("📤 Upload Book (Admin Only)")
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")
    title = st.text_input("Title")
    author = st.text_input("Author")
    course = st.selectbox("Course", ["DS101", "MAT445", "CS501", "Other"])
    isbn = st.text_input("ISBN")
    language = st.text_input("Language")
    year = st.text_input("Published Year")

    if uploaded_file and st.button("Upload"):
        data = uploaded_file.read()
        preview = ""
        try:
            with fitz.open(stream=data, filetype="pdf") as doc:
                preview = doc[0].get_text()
        except: pass
        encoded = base64.b64encode(data).decode()
        book = {
            "title": title,
            "author": author,
            "course": course,
            "isbn": isbn,
            "language": language,
            "published_year": year,
            "file_base64": encoded,
            "file_name": uploaded_file.name,
            "uploaded_at": datetime.utcnow(),
            "preview": preview
        }
        books_col.insert_one(book)

        # Notify all users
        for user in users_col.find({"verified": True}):
            try:
                send_email(user["email"], "New Book Uploaded", f"A new book '{title}' has been added to the library.")
            except: continue
        st.success("✅ Book uploaded and notifications sent")

# --- Search, PDF Preview, Bookmarks, Pagination ---
def search_books():
    st.subheader("🔍 Search Books")
    query = {}
    title = st.text_input("Search by title (partial or full match)", key="search_title")
    if title:
        query["title"] = {"$regex": title, "$options": "i"}

    total = books_col.count_documents(query)
    per_page = 5
    pages = max((total // per_page) + (1 if total % per_page > 0 else 0), 1)
    page = st.number_input("Page", 1, pages, step=1)
    skip = (page - 1) * per_page

    books = books_col.find(query).skip(skip).limit(per_page)
    for book in books:
        with st.expander(book["title"]):
            st.write(f"Author: {book.get('author')}")
            st.write(f"Course: {book.get('course')}")
            st.write(f"ISBN: {book.get('isbn')}")
            st.write(f"Language: {book.get('language')}")
            st.write(f"Year: {book.get('published_year')}")
            if preview := book.get("preview"):
                st.text_area("📖 Preview", preview[:1000], height=200)

            uid = st.session_state.get("user", "guest")
            if uid != "admin":
                fav = fav_col.find_one({"user": uid, "book_id": str(book['_id'])})
                if st.button("⭐ Bookmark" if not fav else "✅ Bookmarked", key=str(book['_id'])):
                    if not fav:
                        fav_col.insert_one({"user": uid, "book_id": str(book['_id'])})
                        st.success("Bookmarked!")

            if st.button(f"📥 Download {book['file_name']}", key=f"dl{book['_id']}"):
                href = f'<a href="data:application/pdf;base64,{book["file_base64"]}" download="{book["file_name"]}">Download PDF</a>'
                st.markdown(href, unsafe_allow_html=True)

# --- Admin Analytics ---
def show_analytics():
    st.subheader("📊 Admin Dashboard")
    st.metric("Books", books_col.count_documents({}))
    st.metric("Users", users_col.count_documents({}))
    st.metric("Downloads", logs_col.count_documents({"type": "download"}))

    data = list(logs_col.find({}, {"_id": 0}))
    if data:
        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        fig = px.histogram(df, x="timestamp", title="Activity Over Time")
        st.plotly_chart(fig)

# --- Main App ---
def main():
    st.set_page_config("📚 DS Book Library", layout="wide")
    set_theme()
    st.title("📚 Data Science Book Library")

    if "user" not in st.session_state:
        choice = st.radio("Choose:", ["Login", "Register"])
        if choice == "Login":
            login_user()
        else:
            register_user()
        if "user" in st.session_state:
            st.experimental_rerun()
        return

    user = st.session_state["user"]
    st.success(f"✅ Logged in as: {user}")
    st.markdown("---")
    search_books()

    if user == "admin":
        st.markdown("---")
        upload_book()
        st.markdown("---")
        show_analytics()

    if st.button("Logout"):
        st.session_state.clear()
        st.experimental_rerun()

if __name__ == "__main__":
    main()
