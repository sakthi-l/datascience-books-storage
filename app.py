""import streamlit as st
import base64
import bcrypt
from pymongo import MongoClient
from datetime import datetime, time
import pandas as pd
import plotly.express as px
from bson import ObjectId
import socket

# --- MongoDB Setup ---
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

# --- Helper to get user IP ---
def get_ip():
    try:
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)
    except:
        return "unknown"

# --- Registration ---
def register_user():
    st.subheader("🌽 Register")
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
    uploaded_file = st.file_uploader("Upload PDF", type="pdf", key="upload_pdf")
    if uploaded_file:
        title = st.text_input("Title", value=uploaded_file.name.rsplit('.', 1)[0], key="upload_title")
        author = st.text_input("Author", key="upload_author")
        language = st.text_input("Language", key="upload_language")

        if st.button("Upload", key="upload_button"):
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

# --- User Dashboard ---
def user_dashboard(user):
    st.subheader("📊 Your Dashboard")
    logs = list(logs_col.find({"user": user}))
    favs = list(fav_col.find({"user": user}))

    if logs:
        df = pd.DataFrame(logs)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        st.write("### 📄 Download History")
        st.dataframe(df[['book', 'author', 'language', 'timestamp']])

    if favs:
        st.write("### ⭐ Bookmarked Books")
        book_ids = [ObjectId(f['book_id']) for f in favs]
        books = books_col.find({"_id": {"$in": book_ids}})
        for book in books:
            st.write(f"📘 {book['title']} by {book.get('author', 'Unknown')}")

# --- Admin Dashboard ---
def admin_dashboard():
    st.subheader("📊 Admin Analytics")
    total_views = logs_col.count_documents({})
    total_downloads = logs_col.count_documents({"type": "download"})
    st.metric("Total Activity", total_views)
    st.metric("Total Downloads", total_downloads)

    logs = list(logs_col.find())
    if logs:
        df = pd.DataFrame(logs)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df_grouped = df.groupby('book').size().reset_index(name='count')
        st.write("### 🔥 Most Accessed Books")
        st.dataframe(df_grouped.sort_values('count', ascending=False))

        st.write("### 📥 Logs")
        st.dataframe(df[['user', 'book', 'timestamp', 'type']])

        st.download_button("Export Logs CSV", df.to_csv(index=False), file_name="logs.csv")

    st.write("### ⭐ Most Bookmarked Books")
    agg = fav_col.aggregate([{"$group": {"_id": "$book_id", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}])
    for row in agg:
        book = books_col.find_one({"_id": ObjectId(row['_id'])})
        if book:
            st.write(f"{book['title']} - {row['count']} bookmarks")

    st.write("### ⬇ Export All Bookmarks")
    favs = list(fav_col.find())
    if favs:
        df = pd.DataFrame(favs)
        st.download_button("Download Bookmarks CSV", df.to_csv(index=False), file_name="bookmarks.csv")

# --- Search and View Books ---
def search_books():
    st.subheader("🔎 Search Books")
    title = st.text_input("Title", key="search_title")
    author = st.text_input("Author", key="search_author")
    language_filter = st.selectbox("Filter by Language", ["All"] + sorted({b.get("language", "") for b in books_col.find()}), key="search_language")

    query = {}
    if title:
        query["title"] = {"$regex": title, "$options": "i"}
    if author:
        query["author"] = {"$regex": author, "$options": "i"}
    if language_filter != "All":
        query["language"] = language_filter

    books = books_col.find(query)
    ip = get_ip()
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    guest_downloads_today = logs_col.count_documents({
        "user": "guest",
        "ip": ip,
        "type": "download",
        "timestamp": {"$gte": today_start}
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

            if can_download:
                st.download_button(
                    label="📄 Download Book",
                    data=base64.b64decode(book["file_base64"]),
                    file_name=book["file_name"],
                    mime="application/pdf",
                    key=f"dl_{book['_id']}"
                )
                logs_col.insert_one({
                    "type": "download",
                    "user": user if user else "guest",
                    "ip": ip,
                    "book": book["title"],
                    "author": book.get("author"),
                    "language": book.get("language"),
                    "timestamp": datetime.utcnow()
                })
            else:
                st.warning("Guests can download only 1 book per day per IP. Please log in for unlimited access.")

# --- Main ---
def main():
    st.set_page_config("📚 PDF Book Library")
    st.title("📚 PDF Book Library")

    search_books()
    st.markdown("---")

    if "user" not in st.session_state:
        choice = st.radio("Choose:", ["Login", "Register"])
        if choice == "Login":
            login_user()
        else:
            register_user()
        return

    user = st.session_state["user"]
    st.success(f"Logged in as: {user}")

    if user == "admin":
        st.markdown("---")
        upload_book()
        st.markdown("---")
        admin_dashboard()
    else:
        st.markdown("---")
        user_dashboard(user)

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

if __name__ == "__main__":
    main()
