from bson import ObjectId
import streamlit as st
import pandas as pd
import datetime
import urllib.parse
from pymongo import MongoClient
from gridfs import GridFS

# MongoDB connection
username = st.secrets["mongodb"]["username"]
password = urllib.parse.quote_plus(st.secrets["mongodb"]["password"])
cluster = st.secrets["mongodb"]["cluster"]
appname = st.secrets["mongodb"]["appname"]

uri = f"mongodb+srv://{username}:{password}@{cluster}/?retryWrites=true&w=majority&appName={appname}"
client = MongoClient(uri)

db = client["ebook_library"]
books_meta = db["books"]
favorites_col = db["favorites"]
logs_col = db["logs"]
users_col = db["users"]
fs = GridFS(db)

# ---------------------- Upload Book ----------------------
def upload_book_ui():
    st.subheader("📤 Upload New Book")
    title = st.text_input("Book Title")
    author = st.text_input("Author")
    course_name = st.selectbox("Course", load_courses())
    keywords = st.text_input("Keywords (comma-separated)")
    isbn = st.text_input("ISBN")
    language = st.text_input("Language")
    published_year = st.text_input("Published Year")
    file = st.file_uploader("Upload PDF", type=["pdf"])

    if st.button("Upload") and file:
        file_id = fs.put(file, filename=file.name)
        books_meta.insert_one({
            "title": title,
            "author": author,
            "course_name": course_name,
            "keywords": [kw.strip() for kw in keywords.split(",")],
            "isbn": isbn,
            "language": language,
            "published_year": published_year,
            "filename": file.name,
            "file_id": file_id,
            "downloads": 0,
            "views": 0
        })
        st.success("✅ Book uploaded successfully!")

# ---------------------- Book Search ----------------------
def search_and_display_books():
    with st.expander("🔍 Advanced Search Filters"):
        search_title = st.text_input("Title")
        author = st.text_input("Author")
        course = st.selectbox("Course", ["--"] + load_courses())
        isbn = st.text_input("ISBN")
        language = st.text_input("Language")
        year = st.text_input("Published Year")

    query = {}
    if search_title:
        query["title"] = {"$regex": search_title, "$options": "i"}
    if author:
        query["author"] = {"$regex": author, "$options": "i"}
    if course and course != "--":
        query["course_name"] = course
    if isbn:
        query["isbn"] = isbn
    if language:
        query["language"] = {"$regex": language, "$options": "i"}
    if year:
        query["published_year"] = year

    results = list(books_meta.find(query))
    if results:
        st.write(f"### {len(results)} result(s) found:")
        for book in results:
            with st.container():
                st.markdown(f"#### 📘 {book.get('title')}")
                st.write(f"**Author:** {book.get('author')}")
                st.write(f"**Course Name:** {book.get('course_name')}")
                st.write(f"**Published Year:** {book.get('published_year')}")

                # Bookmark
                is_bookmarked = favorites_col.find_one({"user": st.session_state.username, "book_ids": book["_id"]})
                if st.button("⭐ Bookmark" if not is_bookmarked else "✅ Bookmarked", key=str(book["_id"])):
                    toggle_bookmark(book["_id"])

                # Download
                st.download_button(
                    label="📥 Download PDF",
                    data=fs.get(book["file_id"]).read(),
                    file_name=book["filename"],
                    mime="application/pdf",
                    on_click=log_download,
                    kwargs={"book_id": str(book["_id"])}
                )
    else:
        st.warning("No matching books found.")

# ---------------------- Bookmark Toggle ----------------------
def toggle_bookmark(book_id):
    entry = favorites_col.find_one({"user": st.session_state.username})
    if not entry:
        favorites_col.insert_one({"user": st.session_state.username, "book_ids": [book_id]})
    elif book_id not in entry["book_ids"]:
        favorites_col.update_one({"user": st.session_state.username}, {"$push": {"book_ids": book_id}})
    else:
        favorites_col.update_one({"user": st.session_state.username}, {"$pull": {"book_ids": book_id}})

# ---------------------- Bookmarked Books ----------------------
def show_bookmarks():
    bookmarks = favorites_col.find_one({"user": st.session_state.username})
    if not bookmarks or not bookmarks.get("book_ids"):
        st.info("You have no bookmarked books yet.")
        return

    book_ids = bookmarks["book_ids"]
    results = list(books_meta.find({"_id": {"$in": book_ids}}))

    for book in results:
        with st.container():
            st.markdown(f"### 📘 {book.get('title')}")
            st.write(f"**Author:** {book.get('author')}")
            st.write(f"**Course Name:** {book.get('course_name')}")
            st.write(f"**Published Year:** {book.get('published_year')}")
            st.download_button(
                label="📥 Download PDF",
                data=fs.get(book["file_id"]).read(),
                file_name=book["filename"],
                mime="application/pdf",
                on_click=log_download,
                kwargs={"book_id": str(book["_id"])}
            )

# ---------------------- Download Logging ----------------------
def increment_download_count(book_id):
    books_meta.update_one(
        {"_id": ObjectId(book_id)},
        {"$inc": {"downloads": 1, "views": 1}}
    )

def log_download(book_id):
    logs_col.insert_one({
        "user": st.session_state.username,
        "book_id": ObjectId(book_id),
        "timestamp": datetime.datetime.now(),
        "action": "download"
    })
    increment_download_count(book_id)

# ---------------------- Download Logs ----------------------
def show_download_logs():
    st.subheader("📥 User Download Logs")
    logs = list(logs_col.find({"action": "download"}).sort("timestamp", -1).limit(100))

    if not logs:
        st.info("No download logs yet.")
        return

    data = []
    for log in logs:
        book = books_meta.find_one({"_id": log["book_id"]})
        data.append({
            "User": log["user"],
            "Book Title": book.get("title") if book else "Deleted Book",
            "Time": log["timestamp"].strftime("%Y-%m-%d %H:%M")
        })

    df = pd.DataFrame(data)
    st.dataframe(df)
    st.download_button("📄 Export Logs", df.to_csv(index=False), "download_logs.csv")

# ---------------------- Book Stats ----------------------
def show_book_stats():
    st.subheader("📈 Most Downloaded Books")
    data = list(books_meta.find({"downloads": {"$gte": 1}}).sort("downloads", -1).limit(10))

    if not data:
        st.info("No download stats yet.")
        return

    rows = [(book.get("title", "Untitled"), book.get("downloads", 0)) for book in data]
    df = pd.DataFrame(rows, columns=["Book Title", "Download Count"])
    st.bar_chart(df.set_index("Book Title"))

# ---------------------- Bookmark Analytics ----------------------
def show_bookmark_analytics():
    st.subheader("⭐ Most Bookmarked Books")
    pipeline = [
        {"$unwind": "$book_ids"},
        {"$group": {"_id": "$book_ids", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    top = list(favorites_col.aggregate(pipeline))
    if not top:
        st.info("No bookmarks yet.")
        return

    book_ids = [b["_id"] for b in top]
    book_map = {b["_id"]: b for b in books_meta.find({"_id": {"$in": book_ids}})}

    titles = [book_map[b["_id"]].get("title", "Untitled") for b in top]
    counts = [b["count"] for b in top]
    df = pd.DataFrame({"Title": titles, "Bookmarks": counts})
    st.bar_chart(df.set_index("Title"))

    total = favorites_col.aggregate([
        {"$unwind": "$book_ids"},
        {"$count": "total"}
    ])
    count = next(total, {}).get("total", 0)
    st.metric("📌 Total Bookmarks", count)

# ---------------------- User Management ----------------------
def show_user_management():
    st.subheader("👥 User Management")
    users = list(users_col.find({}, {"password": 0}))
    if not users:
        st.write("No registered users.")
        return

    for user in users:
        st.write(f"- {user['username']} ({user.get('role', 'user')})")
        if user['username'] != "admin":
            if st.button("❌ Remove User", key=str(user['_id'])):
                users_col.delete_one({"_id": user["_id"]})
                st.experimental_rerun()

    if users:
        df = pd.DataFrame(users)
        st.download_button("📄 Export User List", df.to_csv(index=False), "users.csv")

# ---------------------- Load Courses ----------------------
def load_courses():
    return [
        "MAT445 – Probability & Statistics using R",
        "MAT446R01 – Mathematics for Data Science",
        "BIN522 – Python for Data Science",
        "INT413 – RDBMS, SQL & Visualization",
        "INT531 – Data Mining Techniques",
        "INT530R01 – Artificial Intelligence & Reasoning",
        "INT534R01 – Machine Learning",
        "CSE614R01 – Big Data Mining & Analytics",
        "INT418 – Predictive Analytics Regression & Classification",
        "OEH014 – Ethics & Data Security",
        "INT419R01 – Applied Spatial Data Analytics Using R",
        "ICT601 – Machine Vision",
        "CSE615 – Deep Learning & Applications",
        "INT446 – Generative AI with Large Language Models",
        "BIN533R01 – Healthcare Data Analytics",
        "CSE542 – Social Networks & Graph Analysis"
    ]
