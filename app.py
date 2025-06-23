import streamlit as st
import base64
import bcrypt
import urllib.parse
from pymongo import MongoClient
from datetime import datetime
import pandas as pd
import fitz  # PyMuPDF for PDF previews
import plotly.express as px
from bson import ObjectId

# --- Secrets and MongoDB Setup ---
db_username = st.secrets["mongodb"]["username"]
db_password = st.secrets["mongodb"]["password"]
db_cluster = st.secrets["mongodb"]["cluster"]
db_name = st.secrets["mongodb"]["appname"]
admin_user = st.secrets["mongodb"]["admin_user"]
admin_pass = st.secrets["mongodb"]["admin_pass"]

client = MongoClient(f"mongodb+srv://{db_username}:{db_password}@{db_cluster}/?retryWrites=true&w=majority&appName={db_name}")
db = client["library"]
books_col = db["books"]
users_col = db["users"]
logs_col = db["logs"]
fav_col = db["favorites"]

# --- Theme Toggle ---
def set_theme():
    theme = st.radio("Select Theme", ["Light", "Dark"], horizontal=True, key="theme_toggle")
    if theme == "Dark":
        st.markdown("""
            <style>
                .stApp { background-color: #0E1117; color: white; }
                div[data-testid="stSidebar"] { background-color: #161A23; }
                h1, h2, h3, h4, h5, h6 { color: white !important; }
                input, textarea, .stButton > button { background-color: #2c2f38; color: white; border-color: #444; }
                .stTextInput > div > div > input { background-color: #2c2f38; color: white; }
            </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <style>
                .stApp { background-color: white; color: black; }
                div[data-testid="stSidebar"] { background-color: #F0F2F6; }
                h1, h2, h3, h4, h5, h6 { color: black !important; }
                input, textarea, .stButton > button { background-color: white; color: black; border-color: #ccc; }
                .stTextInput > div > div > input { background-color: white; color: black; }
            </style>
        """, unsafe_allow_html=True)

# --- Register ---
def register_user():
    st.subheader("📝 Register")
    username = st.text_input("Choose a username")
    password = st.text_input("Choose a password", type="password")
    if st.button("Register"):
        if users_col.find_one({"username": username}):
            st.error("❌ Username already exists!")
        else:
            hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            users_col.insert_one({"username": username, "password": hashed_pw, "verified": True, "created_at": datetime.utcnow()})
            st.success("✅ Registered successfully! You can now log in.")

# --- Login ---
def login_user():
    st.subheader("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
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

# --- Upload Book ---
def upload_book():
    st.subheader("📄 Upload Book (Admin Only)")
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")
    title = st.text_input("Title")
    author = st.text_input("Author")
    keywords = st.text_input("Keywords (comma separated)")
    domain = st.text_input("Domain")
    isbn = st.text_input("ISBN")
    language = st.text_input("Language")
    year = st.text_input("Published Year")

    if uploaded_file and st.button("Upload"):
        data = uploaded_file.read()
        encoded = base64.b64encode(data).decode()
        book = {
            "title": title,
            "author": author,
            "keywords": [k.strip() for k in keywords.split(",")],
            "domain": domain,
            "isbn": isbn,
            "language": language,
            "published_year": year,
            "file_base64": encoded,
            "file_name": uploaded_file.name,
            "uploaded_at": datetime.utcnow()
        }
        books_col.insert_one(book)
        st.success("✅ Book uploaded")

# --- Search Books ---
def search_books():
    st.subheader("🔎 Advanced Search")
    query = {}
    title = st.text_input("Title")
    if title:
        query["title"] = {"$regex": title, "$options": "i"}

    books = list(books_col.find(query))
    if not books:
        st.info("No books found.")
        return

    for book in books:
        with st.expander(book["title"]):
            st.write(f"Author: {book.get('author')}")
            st.write(f"Domain: {book.get('domain')}")
            st.write(f"Language: {book.get('language')}")
            pdf_data = book["file_base64"]
            file_url = f"data:application/pdf;base64,{pdf_data}"

            # Open PDF in a new tab
            st.markdown(f"<a href='{file_url}' target='_blank'>📖 View PDF in New Tab</a>", unsafe_allow_html=True)

            user = st.session_state.get("user")
            if user and user != "admin":
                st.download_button("📄 Download this Book", data=base64.b64decode(pdf_data), file_name=book["file_name"], mime="application/pdf")

            elif not user:
                if st.session_state["guest_downloads"] < 3:
                    if st.download_button(f"📥 Guest Download ({3 - st.session_state['guest_downloads']} left)",
                                          data=base64.b64decode(pdf_data),
                                          file_name=book["file_name"], mime="application/pdf",
                                          key=f"guest_dl_{book['_id']}"):
                        st.session_state["guest_downloads"] += 1
                        st.success(f"Downloaded. {3 - st.session_state['guest_downloads']} remaining.")
                else:
                    st.warning("🚫 Guest download limit reached. Please login.")

# --- Admin Dashboard ---
def show_analytics():
    st.subheader("📊 Admin Dashboard")
    st.metric("Books", books_col.count_documents({}))
    st.metric("Users", users_col.count_documents({}))
    st.metric("Downloads", logs_col.count_documents({"type": "download"}))

# --- Manage Users ---
def manage_users():
    st.subheader("👥 Manage Users")
    users = list(users_col.find({}, {"_id": 0, "username": 1, "created_at": 1}))
    if users:
        df = pd.DataFrame(users)
        st.dataframe(df)

# --- Main ---
def main():
    st.set_page_config("📚 DS Book Library", layout="wide")
    set_theme()
    st.title("📚 Data Science Book Library")

    if "guest_downloads" not in st.session_state:
        st.session_state["guest_downloads"] = 0

    search_books()
    st.markdown("---")

    if "user" not in st.session_state:
        choice = st.radio("Choose:", ["Login", "Register"])
        if choice == "Login":
            login_user()
        else:
            register_user()
        if "user" in st.session_state:
            st.rerun()
        return

    user = st.session_state["user"]
    st.success(f"✅ Logged in as: {user}")

    if user == "admin":
        st.markdown("---")
        upload_book()
        st.markdown("---")
        show_analytics()
        st.markdown("---")
        manage_users()

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

if __name__ == "__main__":
    main()
