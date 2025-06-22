import streamlit as st
from pymongo import MongoClient
import base64
import bcrypt
from datetime import datetime
import pandas as pd

# --- MongoDB Connection from secrets ---
db_username = st.secrets["mongodb"]["username"]
db_password = st.secrets["mongodb"]["password"]
db_cluster = st.secrets["mongodb"]["cluster"]
db_name = st.secrets["mongodb"]["appname"]
admin_user = st.secrets["mongodb"]["admin_user"]
admin_pass = st.secrets["mongodb"]["admin_pass"]

client = MongoClient(
    f"mongodb+srv://{db_username}:{db_password}@{db_cluster}/?retryWrites=true&w=majority&appName={db_name}"
)
db = client["library"]
books_col = db["books"]
users_col = db["users"]
logs_col = db["logs"]

# --- Authentication System ---
def register_user():
    st.subheader("📝 Register")
    username = st.text_input("Choose a username")
    password = st.text_input("Choose a password", type="password")
    if st.button("Register"):
        if users_col.find_one({"username": username}):
            st.error("❌ Username already exists!")
        else:
            hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            users_col.insert_one({
                "username": username,
                "password": hashed_pw,
                "created_at": datetime.utcnow()
            })
            st.success("✅ Registered! You can now log in.")

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
            if user and bcrypt.checkpw(password.encode(), user["password"]):
                st.session_state["user"] = username
                st.success(f"✅ Welcome {username}")
            else:
                st.error("❌ Invalid credentials!")

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

# --- Search & Download Books ---
def search_books():
    st.subheader("🔍 Search Books")
    title = st.text_input("Title")
    author = st.text_input("Author")
    course = st.selectbox("Course", ["", "MAT445", "DS101", "CS501", "Other"])
    isbn = st.text_input("ISBN")
    language = st.text_input("Language")
    year = st.text_input("Published Year")

    query = {}
    if title: query["title"] = {"$regex": title, "$options": "i"}
    if author: query["author"] = {"$regex": author, "$options": "i"}
    if course: query["course"] = course
    if isbn: query["isbn"] = {"$regex": isbn, "$options": "i"}
    if language: query["language"] = {"$regex": language, "$options": "i"}
    if year: query["published_year"] = {"$regex": year, "$options": "i"}

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
                        "user": st.session_state.get("user", "guest"),
                        "book": book["title"],
                        "timestamp": datetime.utcnow()
                    })
                    href = f'<a href="data:application/pdf;base64,{book["file_base64"]}" download="{book["file_name"]}">Download PDF</a>'
                    st.markdown(href, unsafe_allow_html=True)
    else:
        st.info("No matching books found.")

# --- Analytics (Admin only) ---
def show_analytics():
    st.subheader("📊 Library Analytics (Admin Only)")
    total_books = books_col.count_documents({})
    total_users = users_col.count_documents({})
    total_downloads = logs_col.count_documents({})
    df_logs = pd.DataFrame(list(logs_col.find({}, {"_id": 0})))
    
    st.metric("📚 Total Books", total_books)
    st.metric("👥 Total Users", total_users)
    st.metric("📥 Total Downloads", total_downloads)

    if not df_logs.empty:
        st.dataframe(df_logs.sort_values("timestamp", ascending=False))
    else:
        st.info("No downloads logged yet.")

# --- Main App ---
def main():
    st.set_page_config("📚 DS Book Library", layout="wide")
    st.title("📚 Data Science Book Library")

    if "user" not in st.session_state:
        login_or_register = st.radio("Choose an action:", ["Login", "Register"])
        if login_or_register == "Login":
            login_user()
        else:
            register_user()
        return  # stop here until logged in

    user = st.session_state["user"]

    st.success(f"✅ Logged in as: {user}")
    st.markdown("---")
    search_books()

    if user == "admin":
        st.markdown("---")
        upload_book()
        st.markdown("---")
        show_analytics()

    if st.button("Logout"):
        st.session_state.clear()
        st.experimental_rerun()

if __name__ == "__main__":
    main()
