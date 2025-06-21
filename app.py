# ---------------- app.py ----------------
import streamlit as st
from auth import register_user, login_user, create_admin_if_not_exists
from upload import (
    upload_book_ui,
    search_and_display_books,
    show_analytics,
    load_courses,
    show_bookmarks,
    show_book_stats,
    show_download_logs
)

st.set_page_config(page_title="Data Science Ebook Library", layout="centered")

create_admin_if_not_exists()

# Theme toggle
if "theme" not in st.session_state:
    st.session_state.theme = "dark"
if st.sidebar.toggle("🌙 Dark Mode", value=True):
    st.markdown("<style>body { background-color: #111; color: #eee; }</style>", unsafe_allow_html=True)
else:
    st.session_state.theme = "light"
    st.markdown("<style>body { background-color: #fff; color: #000; }</style>", unsafe_allow_html=True)

# Sidebar navigation
page = st.sidebar.selectbox("Navigation", ["Login", "Register"])

# Login Page
if page == "Login":
    st.subheader("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        success, role = login_user(username, password)
        if success:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = role
            st.success(f"Welcome {username}!")
        else:
            st.error("Invalid username or password")

# Register Page
elif page == "Register":
    st.subheader("📝 Register")
    new_user = st.text_input("Choose Username")
    new_pass = st.text_input("Choose Password", type="password")

    if st.button("Register"):
        if register_user(new_user, new_pass):
            st.success("Registration successful. Please login.")
        else:
            st.error("Username already exists")

# Role-based dashboard
if st.session_state.get("logged_in"):
    st.sidebar.write(f"Logged in as: {st.session_state.username} ({st.session_state.role})")
    if st.session_state.role == "admin":
        st.title("📚 Admin Dashboard")
        upload_book_ui()
        show_analytics()
        show_book_stats()
        show_download_logs()
    elif st.session_state.role == "user":
        tab = st.sidebar.radio("View", ["Search Books", "My Bookmarks"])
        if tab == "Search Books":
            st.title("📖 Search the Ebook Library")
            search_and_display_books()
        elif tab == "My Bookmarks":
            st.title("⭐ Your Bookmarked Books")
            show_bookmarks()
