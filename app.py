# ---------------- app.py ----------------
import streamlit as st
from upload import (
    upload_book_ui,
    search_and_display_books,
    show_book_stats,
    show_download_logs,
    show_user_management,
    get_total_bookmarks,
    show_bookmark_analytics
)
from pymongo import MongoClient
import urllib.parse

# --- MongoDB Connection ---
username = st.secrets["mongodb"]["username"]
password = urllib.parse.quote_plus(st.secrets["mongodb"]["password"])
cluster = st.secrets["mongodb"]["cluster"]
appname = st.secrets["mongodb"]["appname"]

uri = f"mongodb+srv://{username}:{password}@{cluster}/?retryWrites=true&w=majority&appName={appname}"
client = MongoClient(uri)
db = client["ebook_library"]
users_col = db["users"]

# --- Session State Initialization ---
if "username" not in st.session_state:
    st.session_state.username = ""
    st.session_state.role = ""

# --- Sidebar ---
with st.sidebar:
    st.title("📚 Navigation")
    if st.session_state.username:
        st.write(f"Logged in as: {st.session_state.username} ({st.session_state.role})")
        option = st.radio("Go to", ["🔎 Search", "📤 Upload", "📊 Analytics", "📈 Popular Stats", "📥 Logs", "⭐ Bookmark Analytics"])
        if st.session_state.role == "admin":
            if st.button("👥 User Management"):
                show_user_management()
        if st.button("🚪 Logout"):
            st.session_state.username = ""
            st.session_state.role = ""
            st.rerun()
    else:
        st.subheader("🔐 Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user = users_col.find_one({"username": username, "password": password})
            if user:
                st.session_state.username = user["username"]
                st.session_state.role = user["role"]
                st.success("Logged in successfully")
                st.rerun()
            else:
                st.error("Invalid credentials")
        st.markdown("---")
        st.subheader("📝 Register")
        new_user = st.text_input("New Username")
        new_pass = st.text_input("New Password", type="password")
        if st.button("Register"):
            if users_col.find_one({"username": new_user}):
                st.error("Username already exists")
            else:
                users_col.insert_one({"username": new_user, "password": new_pass, "role": "user"})
                st.success("Registration successful. Please login.")

# --- Main ---
if st.session_state.username:
    if option == "🔎 Search":
        search_and_display_books()
    elif option == "📤 Upload":
        if st.session_state.role == "admin":
            upload_book_ui()
        else:
            st.warning("Only admin can upload books.")
    elif option == "📊 Analytics":
        st.subheader("Analytics Overview")
        total_books = db["books"].count_documents({})
        total_downloads = sum(b.get("downloads", 0) for b in db["books"].find())
        total_bookmarks = get_total_bookmarks()
        st.metric("Total Books", total_books)
        st.metric("Total Downloads", total_downloads)
        st.metric("Total Bookmarks", total_bookmarks)
    elif option == "📈 Popular Stats":
        show_book_stats()
    elif option == "📥 Logs":
        show_download_logs()
    elif option == "⭐ Bookmark Analytics":
        show_bookmark_analytics()
else:
    search_and_display_books()
