import streamlit as st
import base64
import bcrypt
from pymongo import MongoClient
from datetime import datetime
import pandas as pd
import plotly.express as px
from bson import ObjectId

# --- MongoDB Setup (use your own secrets or credentials) ---
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

# --- Registration ---
def register_user():
    st.subheader("📝 Register")
    username = st.text_input("Username", key="reg_username")
    password = st.text_input("Password", type="password", key="reg_password")
    if st.button("Register"):
        if users_col.find_one({"username": username}):
            st.error("Username already exists")
        else:
            hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            users_col.insert_one({
                "username": username,
                "password": hashed_pw,
                "verified": True,
                "created_at": datetime.utcnow()
            })
            st.success("Registered successfully")

# --- Login ---
def login_user():
    st.subheader("🔐 Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Login"):
        if username == admin_user and password == admin_pass:
            st.session_state["user"] = "admin"
            st.success("Logged in as Admin")
        else:
            user = users_col.find_one({"username": username})
            if user and user.get("verified") and bcrypt.checkpw(password.encode(), user["password"]):
                st.session_state["user"] = username
                st.success(f"Welcome {username}")
            else:
                st.error("Invalid or unverified credentials")

# --- Upload Book (Admin Only) ---
def upload_book():
    st.subheader("📄 Upload Book")
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")
    if uploaded_file:
        title = st.text_input("Title")
        author = st.text_input("Author")
        language = st.text_input("Language")

        if st.button("Upload"):
            data = uploaded_file.read()
            if len(data) == 0:
                st.error("File is empty")
                return

            encoded = base64.b64encode(data).decode("utf-8")
            books_col.insert_one({
                "title": title,
                "author": author,
                "language": language,
                "file_name": uploaded_file.name,
                "file_base64": encoded,
                "uploaded_at": datetime.utcnow()
            })
            st.success("Book uploaded")

# --- Search and View Books ---
def search_books():
    st.subheader("🔎 Search Books")
    title = st.text_input("Title")
    author = st.text_input("Author")
    language_filter = st.selectbox("Filter by Language", ["All"] + sorted({b.get("language", "") for b in books_col.find()}))

    query = {}
    if title:
        query["title"] = {"$regex": title, "$options": "i"}
    if author:
        query["author"] = {"$regex": author, "$options": "i"}
    if language_filter != "All":
        query["language"] = language_filter

    books = books_col.find(query)
    today = datetime.utcnow().date()
    guest_downloads_today = logs_col.count_documents({
        "user": "guest",
        "type": "download",
        "timestamp": {"$gte": datetime(today.year, today.month, today.day)}
    })

    for book in books:
        with st.expander(book["title"]):
            st.write(f"Author: {book.get('author')}")
            st.write(f"Language: {book.get('language')}")

            user = st.session_state.get("user")
            can_download = user or guest_downloads_today < 1

            if st.button("⭐ Bookmark", key=f"fav_{book['_id']}"):
                if user:
                    fav_col.update_one(
                        {"user": user, "book_id": str(book['_id'])},
                        {"$set": {"timestamp": datetime.utcnow()}},
                        upsert=True
                    )
                    st.success("Bookmarked")
                else:
                    st.warning("Login to bookmark books")

            can_download = user or guest_downloads_today < 1

            if can_download:
                if st.download_button(
        label="📂 Download This Book",
        data=base64.b64decode(book["file_base64"]),
        file_name=book["file_name"],
        mime="application/pdf",
        key=f"download_{book['_id']}"
    ):
                logs_col.insert_one({
            "type": "download",
            "user": user if user else "guest",
            "book": book["title"],
            "author": book.get("author"),
            "language": book.get("language"),
            "timestamp": datetime.utcnow()
        })
            else:
                st.warning("Guests can download only 1 book per day. Please log in for unlimited access.")

            
# --- Admin Analytics ---
def show_analytics():
    st.subheader("📊 Analytics")
    total_views = logs_col.count_documents({"type": "view"})
    total_downloads = logs_col.count_documents({"type": "download"})

    st.metric("Total Views", total_views)
    st.metric("Total Downloads", total_downloads)

    logs = list(logs_col.find())
    if logs:
        df = pd.DataFrame(logs)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        authors = ["All"] + sorted(df["author"].dropna().unique())
        selected_author = st.selectbox("Filter by Author", authors, key="analytics_author")

        languages = ["All"] + sorted(df["language"].dropna().unique())
        selected_language = st.selectbox("Filter by Language", languages, key="analytics_language")

        if selected_author != "All":
            df = df[df["author"] == selected_author]
        if selected_language != "All":
            df = df[df["language"] == selected_language]

        st.dataframe(df[["user", "book", "author", "language", "type", "timestamp"]])

        fig = px.histogram(df, x="timestamp", color="type", title="User Activity Over Time")
        st.plotly_chart(fig)
    else:
        st.info("No logs to display.")

# --- User Dashboard ---
def user_dashboard():
    st.subheader("📂 My Download History")
    user = st.session_state.get("user")
    if not user or user == "admin":
        st.warning("Login as a regular user to view your dashboard.")
        return

    logs = list(logs_col.find({"user": user, "type": "download"}, {"_id": 0}))
    if logs:
        df = pd.DataFrame(logs)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp", ascending=False)
        st.dataframe(df)
    else:
        st.info("No download activity yet.")

    st.subheader("⭐ My Bookmarks")
    favs = fav_col.find({"user": user})
    for fav in favs:
        book = books_col.find_one({"_id": ObjectId(fav["book_id"])})
        if book:
            st.write(f"📘 {book['title']} ({book.get('language', '')})")

# --- Main ---
def main():
    st.set_page_config("📚 PDF Book Library", layout="wide")
    st.title("📚 PDF Book Library")

    # Display trending books
    st.subheader("🔥 Trending Books")
    data = list(logs_col.find({}, {"_id": 0}))
    if data:
        df = pd.DataFrame(data)
        trending = df[df["type"] == "download"].groupby("book").size().sort_values(ascending=False).head(3)
        for title in trending.index:
            st.write(f"📘 {title}")

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

    if st.session_state["user"] == "admin":
        upload_book()
        show_analytics()
    else:
        user_dashboard()

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

if __name__ == "__main__":
    main()
