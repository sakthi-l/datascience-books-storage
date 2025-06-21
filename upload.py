# ---------------- upload.py ----------------
from bson import ObjectId
import streamlit as st
import pandas as pd
import datetime
import urllib.parse
from pymongo import MongoClient
from gridfs import GridFS
import fitz  # pymupdf for reading PDF content

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

def upload_book_ui():
    st.subheader("📤 Upload a New Book (PDF)")
    uploaded_file = st.file_uploader("Select PDF File", type="pdf")
    if uploaded_file:
        title = st.text_input("Title")
        author = st.text_input("Author")
        course_name = st.selectbox("Course Name", ["--"] + load_courses())
        keywords = st.text_input("Keywords (comma-separated)")
        isbn = st.text_input("ISBN")
        language = st.text_input("Language")
        year = st.text_input("Published Year")

        if st.button("Upload"):
            file_id = fs.put(uploaded_file, filename=uploaded_file.name)
            books_meta.insert_one({
                "title": title,
                "author": author,
                "course_name": course_name,
                "keywords": [kw.strip() for kw in keywords.split(",")],
                "isbn": isbn,
                "language": language,
                "published_year": year,
                "filename": uploaded_file.name,
                "file_id": file_id,
                "downloads": 0,
                "views": 0
            })
            st.success("Book uploaded successfully!")

def toggle_bookmark(book_id):
    existing = favorites_col.find_one({"user": st.session_state.username})
    if existing:
        if book_id in existing.get("book_ids", []):
            favorites_col.update_one({"user": st.session_state.username}, {"$pull": {"book_ids": book_id}})
        else:
            favorites_col.update_one({"user": st.session_state.username}, {"$addToSet": {"book_ids": book_id}})
    else:
        favorites_col.insert_one({"user": st.session_state.username, "book_ids": [book_id]})

def log_download(book_id):
    logs_col.insert_one({
        "user": st.session_state.username,
        "book_id": ObjectId(book_id),
        "timestamp": datetime.datetime.now(),
        "action": "download"
    })
    books_meta.update_one({"_id": ObjectId(book_id)}, {"$inc": {"downloads": 1}})

def search_and_display_books():
    st.header("📚 Data Science eBook Library")
    st.subheader("🔎 Search for Books")
    title_input = st.text_input("Search by title", key="basic_title")

    with st.expander("🔍 Advanced Search Filters"):
        author = st.text_input("Author", key="search_author")
        course = st.selectbox("Course", ["--"] + load_courses(), key="search_course")
        isbn = st.text_input("ISBN", key="search_isbn")
        language = st.text_input("Language", key="search_language")
        year = st.text_input("Published Year", key="search_year")

    query = {}
    if title_input:
        query["title"] = {"$regex": title_input, "$options": "i"}
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

                is_bookmarked = favorites_col.find_one({"user": st.session_state.username, "book_ids": book["_id"]})
                if st.button("⭐ Bookmark" if not is_bookmarked else "✅ Bookmarked", key=f"bookmark_{book['_id']}"):
                    toggle_bookmark(book["_id"])

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
