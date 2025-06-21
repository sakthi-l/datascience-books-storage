import streamlit as st
from auth import register_user, login_user, create_admin_if_not_exists
from upload import upload_book_ui

st.set_page_config(page_title="Data Science Ebook Library", layout="centered")

create_admin_if_not_exists()

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
    elif st.session_state.role == "user":
        st.title("📖 Welcome to the Ebook Library")
        st.info("Book viewing and download will be available in the next steps.")
