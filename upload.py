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
fs = GridFS(db)

def search_and_display_books():
    search_title = st.text_input("🔎 Enter book title")
    if search_title:
        matches = books_meta.find({"title": {"$regex": search_title, "$options": "i"}})
        results = list(matches)
        if results:
            st.write(f"### {len(results)} result(s) found:")
            for book in results:
                with st.container():
                    st.markdown(f"#### 📘 {book.get('title')}")
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
        else:
            st.warning("No matching books found.")

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

def show_book_stats():
    st.subheader("📈 Popular Books Stats")
    st.write("Most Downloaded Books:")
    data = list(books_meta.find({"downloads": {"$gte": 1}}).sort("downloads", -1).limit(10))

    if not data:
        st.info("No download stats yet.")
        return

    rows = [(book.get("title", "Untitled"), book.get("downloads", 0)) for book in data]
    df = pd.DataFrame(rows, columns=["Book Title", "Download Count"])
    st.bar_chart(df.set_index("Book Title"))

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
