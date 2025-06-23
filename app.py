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
import streamlit.components.v1 as components
import tempfile
import base64

import streamlit.components.v1 as components

def search_books():
    st.subheader("🔎 Advanced Search")
    query = {}
    col1, col2 = st.columns(2)
    with col1:
        title = st.text_input("Title", key="search_title")
        author = st.text_input("Author", key="search_author")
        keywords = st.text_input("Keywords", key="search_keywords")
        domain = st.text_input("Domain", key="search_domain")
    with col2:
        isbn = st.text_input("ISBN", key="search_isbn")
        language = st.text_input("Language", key="search_language")
        year = st.text_input("Published Year", key="search_year")

    if title:
        query["title"] = {"$regex": title, "$options": "i"}
    if author:
        query["author"] = {"$regex": author, "$options": "i"}
    if keywords:
        query["keywords"] = {"$in": [k.strip() for k in keywords.split(",")]}
    if domain:
        query["domain"] = {"$regex": domain, "$options": "i"}
    if isbn:
        query["isbn"] = {"$regex": isbn, "$options": "i"}
    if language:
        query["language"] = {"$regex": language, "$options": "i"}
    if year:
        query["published_year"] = year

    books = list(books_col.find(query))
    if not books:
        st.info("No books matched your query.")
        return

    for book in books:
        with st.expander(book["title"]):
            st.write(f"**Author:** {book.get('author')}")
            st.write(f"**Keywords:** {', '.join(book.get('keywords', []))}")
            st.write(f"**Domain:** {book.get('domain')}")
            st.write(f"**ISBN:** {book.get('isbn')}")
            st.write(f"**Language:** {book.get('language')}")
            st.write(f"**Year:** {book.get('published_year')}")

            # 👁️ View full PDF (inline, works for all users)
            if st.button(f"📖 View PDF – {book['file_name']}", key=f"view_{book['_id']}"):
                st.markdown(
                    f'<iframe src="data:application/pdf;base64,{book["file_base64"]}" '
                    f'width="100%" height="700px" style="border: none;"></iframe>',
                    unsafe_allow_html=True
                )

            # 🔒 Allow download only for logged-in users
            user = st.session_state.get("user")
            if user and user != "admin":
                st.download_button(
                    label="📄 Download this Book",
                    data=base64.b64decode(book["file_base64"]),
                    file_name=book["file_name"],
                    mime="application/pdf"
                )

                fav = fav_col.find_one({"user": user, "book_id": str(book['_id'])})
                if st.button("⭐ Bookmark" if not fav else "✅ Bookmarked", key=f"fav_{book['_id']}"):
                    if not fav:
                        fav_col.insert_one({"user": user, "book_id": str(book['_id'])})
                        st.success("Bookmarked!")

            elif user == "admin":
                st.info("Admin access granted. Download/bookmark not shown.")
            else:
                st.warning("🔐 Please log in to download or bookmark this book.")

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
