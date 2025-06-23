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
        st.markdown("""<style>
            .stApp { background-color: #0E1117; color: white; }
            div[data-testid="stSidebar"] { background-color: #161A23; }
            h1, h2, h3, h4, h5, h6, .css-10trblm, .css-1v3fvcr { color: white !important; }
            input, textarea, .stButton > button { background-color: #2c2f38; color: white; border-color: #444; }
            .stTextInput > div > div > input { background-color: #2c2f38; color: white; }
        </style>""", unsafe_allow_html=True)
    else:
        st.markdown("""<style>
            .stApp { background-color: white; color: black; }
            div[data-testid="stSidebar"] { background-color: #F0F2F6; }
            h1, h2, h3, h4, h5, h6, .css-10trblm, .css-1v3fvcr { color: black !important; }
            input, textarea, .stButton > button { background-color: white; color: black; border-color: #ccc; }
            .stTextInput > div > div > input { background-color: white; color: black; }
        </style>""", unsafe_allow_html=True)

# --- Registration ---
def register_user():
    st.markdown('<h3 style="font-size:24px;">📝 Register</h3>', unsafe_allow_html=True)
    username = st.text_input("Choose a username", key="reg_username")
    password = st.text_input("Choose a password", type="password", key="reg_password")
    if st.button("Register", key="reg_button"):
        if users_col.find_one({"username": username}):
            st.error("❌ Username already exists!")
        else:
            hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            users_col.insert_one({
                "username": username,
                "password": hashed_pw,
                "verified": True,
                "created_at": datetime.utcnow()
            })
            st.success("✅ Registered successfully! You can now log in.")

# --- Login ---
def login_user():
    st.markdown('<h3 style="font-size:24px;">🔐 Login</h3>', unsafe_allow_html=True)
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Login", key="login_button"):
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
    st.markdown('<h3 style="font-size:24px;">📄 Upload Book (Admin Only)</h3>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload PDF", type="pdf", key="pdf_uploader")
    title = st.text_input("Title", key="upload_title")
    author = st.text_input("Author", key="upload_author")
    keywords = st.text_input("Keywords (comma separated)", key="upload_keywords")
    domain = st.text_input("Domain", key="upload_domain")
    isbn = st.text_input("ISBN", key="upload_isbn")
    language = st.text_input("Language", key="upload_language")
    year = st.text_input("Published Year", key="upload_year")

    if uploaded_file and st.button("Upload", key="upload_button"):
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
            "keywords": [k.strip() for k in keywords.split(",")],
            "domain": domain,
            "isbn": isbn,
            "language": language,
            "published_year": year,
            "file_base64": encoded,
            "file_name": uploaded_file.name,
            "uploaded_at": datetime.utcnow(),
            "preview": preview
        }
        books_col.insert_one(book)
        st.success("✅ Book uploaded")
from PIL import Image
import io

def show_pdf_page_as_image(encoded_base64, title):
    try:
        pdf_data = base64.b64decode(encoded_base64)
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # High-res
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        st.image(img, caption=f"📖 {title} – First Page Preview", use_column_width=True)
    except Exception as e:
        st.error("❌ Failed to render PDF preview.")

# --- Search Books ---
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

            # 👁️ Show first page image preview
            show_pdf_page_as_image(book["file_base64"], book["title"])

            # 📖 View full PDF (visible to all)
            if st.button(f"📖 View PDF – {book['file_name']}", key=f"view_{book['_id']}"):
                pdf_link = f'<iframe src="data:application/pdf;base64,{book["file_base64"]}" width="100%" height="700px"></iframe>'
                st.markdown(pdf_link, unsafe_allow_html=True)

            # 🔒 Download only for logged-in users
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
    st.markdown('<h3 style="font-size:24px;">📊 Admin Dashboard</h3>', unsafe_allow_html=True)
    st.metric("Books", books_col.count_documents({}))
    st.metric("Users", users_col.count_documents({}))
    st.metric("Downloads", logs_col.count_documents({"type": "download"}))
    data = list(logs_col.find({}, {"_id": 0}))
    if data:
        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        fig = px.histogram(df, x="timestamp", title="Activity Over Time")
        st.plotly_chart(fig)

# --- Admin: Manage Users ---
def manage_users():
    st.markdown('<h3 style="font-size:24px;">👥 Manage Users</h3>', unsafe_allow_html=True)
    users = list(users_col.find({}, {"_id": 0, "username": 1, "created_at": 1}))
    if users:
        df = pd.DataFrame(users)
        st.dataframe(df)

        usernames = [u["username"] for u in users if u["username"] != "admin"]
        selected_user = st.selectbox("Select user to delete", usernames)

        if st.button("❌ Delete User"):
            users_col.delete_one({"username": selected_user})
            fav_col.delete_many({"user": selected_user})
            logs_col.delete_many({"user": selected_user})
            st.success(f"User '{selected_user}' deleted.")
            st.rerun()
    else:
        st.info("No registered users found.")

# --- Main ---
def main():
    st.set_page_config("📚 DS Book Library", layout="wide")
    set_theme()
    st.markdown('<h1 style="font-size:32px;">📚 Data Science Book Library</h1>', unsafe_allow_html=True)
    search_books()
    st.markdown("---")

    if "user" not in st.session_state:
        choice = st.radio("Choose:", ["Login", "Register"], key="auth_radio")
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
