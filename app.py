import streamlit as st
from auth import register_user, login_user, create_admin_if_not_exists
from upload import (
    upload_book_ui,
    search_and_display_books,
    show_book_stats,
    show_download_logs,
    show_user_management,
    get_total_bookmarks,
    show_bookmark_analytics
)

# Ensure admin account exists
create_admin_if_not_exists()

# Session state setup
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None

# App Title and Search (Always visible)
st.title("📚 Data Science eBook Library")

st.subheader("🔎 Search for Books")
search_and_display_books()

st.divider()

# Login Form
if not st.session_state.logged_in:
    with st.expander("🔐 Login to access more features", expanded=True):
        st.subheader("🔐 Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            success, role = login_user(username, password)
            if success:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = role
                st.success(f"Logged in as: {username} ({role})")
                st.rerun()
            else:
                st.error("Invalid username or password")

        st.markdown("---")
        st.subheader("🆕 Register")
        new_user = st.text_input("New Username")
        new_pass = st.text_input("New Password", type="password")
        if st.button("Register"):
            if register_user(new_user, new_pass):
                st.success("User registered successfully. You can now login.")
            else:
                st.warning("Username already exists.")

# Admin/User Dashboard
if st.session_state.logged_in:
    st.sidebar.title("Navigation")
    role = st.session_state.role
    username = st.session_state.username
    st.sidebar.write(f"Logged in as: {username} ({role})")

    menu = [
        "🔎 Search", "📤 Upload", "⭐ Bookmarks", "📊 Analytics", "📈 Popular Stats",
        "📥 Logs", "⭐ Bookmark Analytics", "👥 User Management", "🚪 Logout"
    ]
    choice = st.sidebar.radio("Go to", menu)

    if choice == "🔎 Search":
        st.subheader("🔎 Search for Books")
        search_and_display_books()

    elif choice == "📤 Upload" and role == "admin":
        upload_book_ui()

    elif choice == "⭐ Bookmarks":
        show_bookmarks()

    elif choice == "📊 Analytics" and role == "admin":
        show_analytics()

    elif choice == "📈 Popular Stats" and role == "admin":
        show_book_stats()

    elif choice == "📥 Logs" and role == "admin":
        show_download_logs()

    elif choice == "⭐ Bookmark Analytics" and role == "admin":
        show_bookmark_analytics()

    elif choice == "👥 User Management" and role == "admin":
        show_user_management()

    elif choice == "🚪 Logout":
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.role = None
        st.success("Logged out successfully.")
        st.rerun()

    else:
        st.warning("You do not have access to this section.")
