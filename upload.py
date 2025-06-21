import fitz  # PyMuPDF
import streamlit as st
import gridfs
import datetime
from pymongo import MongoClient
import urllib.parse

# MongoDB connection
username = st.secrets["mongodb"]["username"]
password = urllib.parse.quote_plus(st.secrets["mongodb"]["password"])
cluster = st.secrets["mongodb"]["cluster"]
appname = st.secrets["mongodb"]["appname"]

client = MongoClient(f"mongodb+srv://{username}:{password}@{cluster}/?retryWrites=true&w=majority&appName={appname}")
db = client["ebook_library"]
fs = gridfs.GridFS(db)
books_meta = db["books_metadata"]

def extract_pdf_metadata(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = "".join([page.get_text() for page in doc[:5]])
    metadata = doc.metadata
    return {
        "title": metadata.get("title") or text[:100].strip(),
        "author": metadata.get("author") or "Unknown",
        "keywords": metadata.get("keywords") or "data science",
        "isbn": "Unknown",
        "language": "English",
        "course_name": "General",
        "published_year": 2024
    }

def upload_book_ui():
    st.subheader("📤 Upload PDF Book")
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")

    if uploaded_file:
        file_bytes = uploaded_file.read()
        metadata = extract_pdf_metadata(file_bytes)

        if st.button("Save Book"):
            file_id = fs.put(file_bytes, filename=uploaded_file.name)
            metadata.update({
                "file_id": file_id,
                "filename": uploaded_file.name,
                "uploaded_by": st.session_state["username"],
                "uploaded_at": datetime.datetime.now()
            })
            books_meta.insert_one(metadata)
            st.success("Book uploaded successfully!")
from bson import ObjectId
import datetime

logs_col = db["logs"]


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
