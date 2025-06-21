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
