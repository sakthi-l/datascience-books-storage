import streamlit as st
from pymongo import MongoClient
import base64
import bcrypt
from datetime import datetime, timedelta
import pandas as pd
import smtplib
from email.message import EmailMessage
import random

# --- Config & Secrets ---
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

client = MongoClient(
    f"mongodb+srv://{db_username}:{db_password}@{db_cluster}/?retryWrites=true&w=majority&appName={db_name}"
)
db = client["library"]
books_col = db["books"]
users_col = db["users"]
logs_col = db["logs"]
otp_col = db["otp_collection"]

# --- Helper functions for email OTP ---
def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp_email(to_email, otp):
    msg = EmailMessage()
    msg.set_content(f"Your OTP for password reset is: {otp}")
    msg["Subject"] = "Password Reset OTP"
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)

# --- Authentication ---
def register_user():
    st.subheader("📝 Register")
    username = st.text_input("Choose a username", key="reg_username")
    password = st.text_input("Choose a password", type="password", key="reg_password")
    email = st.text_input("Enter your email (for password reset)", key="reg_email")
    if st.button("Register"):
        if users_col.find_one({"username": username}):
            st.error("❌ Username already exists!")
        else:
            hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            users_col.insert_one({
                "username": username,
                "password": hashed_pw,
                "email": email,
                "created_at": datetime.utcnow()
            })
            st.success("✅ Registered! You can now log in.")

def login_user():
    st.subheader("🔐 Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    forgot_pw = st.button("Forgot Password?")
    if forgot_pw:
        st.session_state["forgot_pw_user"] = username
        st.session_state["show_forgot_pw"] = True
    if st.button("Login"):
        if username == admin_user and password == admin_pass:
            st.session_state["user"] = "admin"
            st.success("🛡️ Logged in as Admin")
        else:
            user = users_col.find_one({"username": username})
            if user and bcrypt.checkpw(password.encode(), user["password"]):
                st.session_state["user"] = username
                st.success(f"✅ Welcome {username}")
            else:
                st.error("❌ Invalid credentials!")

def forgot_password():
    st.subheader("🔐 Forgot Password")
    username = st.session_state.get("forgot_pw_user", "")
    if not username:
        username = st.text_input("Enter your username")
    else:
        st.text(f"Username: **{username}**")

    if st.button("Send OTP"):
        user = users_col.find_one({"username": username})
        if user and user.get("email"):
            otp = generate_otp()
            otp_doc = {
                "username": username,
                "otp": otp,
                "expires_at": datetime.utcnow() + timedelta(minutes=10)
            }
            otp_col.replace_one({"username": username}, otp_doc, upsert=True)
            try:
                send_otp_email(user["email"], otp)
                st.success(f"OTP sent to {user['email']}. Please check your inbox.")
                st.session_state["forgot_pw_user"] = username
                st.session_state["show_otp_input"] = True
            except Exception as e:
                st.error(f"Failed to send OTP email: {e}")
        else:
            st.error("Username not found or email not set.")

    if st.session_state.get("show_otp_input", False):
        entered_otp = st.text_input("Enter OTP")
        new_password = st.text_input("Enter new password", type="password")
        if st.button("Reset Password"):
            otp_doc = otp_col.find_one({"username": username})
            if otp_doc and otp_doc["otp"] == entered_otp and datetime.utcnow() < otp_doc["expires_at"]:
                hashed_pw = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
                users_col.update_one({"username": username}, {"$set": {"password": hashed_pw}})
                otp_col.delete_one({"username": username})
                st.success("Password reset successful! Please log in.")
                # Clear forgot pw session state
                st.session_state["show_forgot_pw"] = False
                st.session_state["show_otp_input"] = False
                st.session_state.pop("forgot_pw_user", None)
            else:
                st.error("Invalid or expired OTP.")

# --- Upload Section (Admin only) ---
def upload_book():
    st.subheader("📤 Upload New Book (Admin Only)")
    uploaded_file = st.file_uploader("Choose a PDF", type="pdf")
    title = st.text_input("Title")
    author = st.text_input("Author")
    course = st.selectbox("Course", ["MAT445", "DS101", "CS501", "Other"])
    isbn = st.text_input("ISBN")
    language = st.text_input("Language")
    year = st.text_input("Published Year")

    if uploaded_file and st.button("Upload"):
        file_data = uploaded_file.read()
        file_b64 = base64.b64encode(file_data).decode()
        book = {
            "title": title.strip(),
            "author": author.strip(),
            "course": course,
            "isbn": isbn.strip(),
            "language": language.strip(),
            "published_year": year.strip(),
            "file_base64": file_b64,
            "file_name": uploaded_file.name,
            "uploaded_at": datetime.utcnow()
        }
        books_col.insert_one(book)
        st.success(f"✅ Uploaded '{title}'")

# --- Search & Download ---
def search_books():
    st.subheader("🔍 Search Books")
    title = st.text_input("Title")
    author = st.text_input("Author")

    courses = books_col.distinct("course")
    languages = books_col.distinct("language")
    years = books_col.distinct("published_year")

    course = st.multiselect("Course", courses)
    language = st.multiselect("Language", languages)
    year = st.multiselect("Published Year", years)
    isbn = st.text_input("ISBN")

    query = {}
    if title: query["title"] = {"$regex": title, "$options": "i"}
    if author: query["author"] = {"$regex": author, "$options": "i"}
    if course: query["course"] = {"$in": course}
    if language: query["language"] = {"$in": language}
    if year: query["published_year"] = {"$in": year}
    if isbn: query["isbn"] = {"$regex": isbn, "$options": "i"}

    if st.session_state["user"] != "admin":
        logs_col.insert_one({
            "type": "search",
            "user": st.session_state["user"],
            "query": query,
            "timestamp": datetime.utcnow()
        })

    results = list(books_col.find(query))
    if results:
        for book in results:
            with st.expander(book["title"]):
                st.write(f"**Author:** {book.get('author')}")
                st.write(f"**Course:** {book.get('course')}")
                st.write(f"**ISBN:** {book.get('isbn')}")
                st.write(f"**Language:** {book.get('language')}")
                st.write(f"**Year:** {book.get('published_year')}")
                if st.button(f"📥 Download {book['file_name']}", key=str(book['_id'])):
                    logs_col.insert_one({
                        "type": "download",
                        "user": st.session_state.get("user", "guest"),
                        "book": book["title"],
                        "timestamp": datetime.utcnow()
                    })
                    href = f'<a href="data:application/pdf;base64,{book["file_base64"]}" download="{book["file_name"]}">Download PDF</a>'
                    st.markdown(href, unsafe_allow_html=True)
    else:
        st.info("No matching books found.")

# --- Analytics (Admin) ---
def show_analytics():
    st.subheader("📊 Library Analytics (Admin Only)")
    st.metric("📚 Books", books_col.count_documents({}))
    st.metric("👥 Users", users_col.count_documents({}))
    st.metric("📥 Downloads", logs_col.count_documents({"type": "download"}))

    df = pd.DataFrame(list(logs_col.find({"type": "download"}, {"_id": 0})))
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(df.sort_values("timestamp", ascending=False))
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📤 Export Logs as CSV", data=csv, file_name="download_logs.csv", mime="text/csv")
    else:
        st.info("No downloads yet.")

# --- Search History Viewer (User) ---
def view_user_history():
    st.subheader("🕓 My Search History")
    user = st.session_state["user"]
    logs = list(logs_col.find({"type": "search", "user": user}, {"_id": 0, "query": 1, "timestamp": 1}))
    if logs:
        df = pd.DataFrame(logs)
        df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(df.sort_values("timestamp", ascending=False))
    else:
        st.info("No search history yet.")

# --- Admin-Only Password Reset ---
def reset_user_password():
    st.subheader("🔁 Reset User Password (Admin Only)")
    username = st.text_input("Target Username")
    new_pw = st.text_input("New Password", type="password")
    if st.button("Reset Password"):
        user = users_col.find_one({"username": username})
        if user:
            hashed_pw = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt())
            users_col.update_one({"username": username}, {"$set": {"password": hashed_pw}})
            st.success(f"✅ Password for '{username}' reset.")
        else:
            st.error("❌ Username not found.")

# --- Main ---
def main():
    st.set_page_config("📚 DS Book Library", layout="centered")
    st.title("📚 Data Science Book Library")

    # Show forgot password UI if needed
    if st.session_state.get("show_forgot_pw", False):
        forgot_password()
        return

    if "user" not in st.session_state:
        login_or_register = st.radio("Choose an action:", ["Login", "Register"])
        if login_or_register == "Login":
            login_user()
        else:
            register_user()
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
        st.markdown("---")
        reset_user_password()
    else:
        st.markdown("---")
        view_user_history()

    if st.button("Logout"):
        st.session_state.clear()
        st.experimental_rerun()

if __name__ == "__main__":
    main()
