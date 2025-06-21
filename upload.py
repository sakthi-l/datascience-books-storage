from bson import ObjectId
import streamlit as st
import pandas as pd
import datetime
import urllib.parse
from pymongo import MongoClient
from gridfs import GridFS

# ------------------------------
# MongoDB Connection
# ------------------------------
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

# ------------------------------
# Helper: Load Course List
# ------------------------------
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

# ------------------------------
# Upload UI
# ------------------------------
def upload_book_ui():
    st.subheader("📄 Upload a New Book (PDF)")
    uploaded_file = st.file_uploader("Select PDF File", type="pdf")

    if uploaded_file:
        # Fetch distinct values from MongoDB
        existing_titles = books_meta.distinct("title")
        existing_authors = books_meta.distinct("author")
        existing_keywords = books_meta.distinct("keywords")

        # Title Suggestion
        title = st.selectbox(
            "Title (select existing or type new)",
            options=sorted(existing_titles) + ["<New Title>"],
            index=len(existing_titles),
            key="book_title"
        )
        if title == "<New Title>":
            title = st.text_input("Enter New Title", key="custom_title")

        # Author Suggestion
        author = st.selectbox(
            "Author (select existing or type new)",
            options=sorted(set(filter(None, existing_authors))) + ["<New Author>"],
            index=len(set(existing_authors)),
            key="book_author"
        )
        if author == "<New Author>":
            author = st.text_input("Enter New Author", key="custom_author")

        # Course Selection
        course_name = st.selectbox("Course Name", ["--"] + load_courses())

        # Keyword Suggestion
        flat_keywords = sorted({kw.strip() for kws in existing_keywords if isinstance(kws, list) for kw in kws})
        keyword_input = st.multiselect(
            "Keywords (choose or type new)",
            options=flat_keywords,
            key="book_keywords"
        )

        isbn = st.text_input("ISBN")
        language = st.text_input("Language")
        year = st.text_input("Published Year")

        if st.button("Upload"):
            # Duplicate check
            existing = books_meta.find_one({
                "title": title.strip(),
                "course_name": course_name.strip()
            })
            if existing:
                st.error("❌ A book with the same title and course already exists.")
                return

            # Store file in GridFS and save metadata
            file_id = fs.put(uploaded_file, filename=uploaded_file.name)
            books_meta.insert_one({
                "title": title.strip(),
                "author": author.strip(),
                "course_name": course_name.strip(),
                "keywords": [kw.strip() for kw in keyword_input if kw.strip()],
                "isbn": isbn.strip(),
                "language": language.strip(),
                "published_year": year.strip(),
                "filename": uploaded_file.name,
                "file_id": file_id,
                "downloads": 0,
                "views": 0
            })
            st.success("✅ Book uploaded successfully!")


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
    search_triggered = st.button("🔍 Search")

    with st.expander("🔍 Advanced Search Filters"):
        author = st.text_input("Author", key="search_author")
        course = st.selectbox("Course", ["--"] + load_courses(), key="search_course")
        isbn = st.text_input("ISBN", key="search_isbn")
        language = st.text_input("Language", key="search_language")
        year = st.text_input("Published Year", key="search_year")

    if search_triggered:
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
    key=f"download_{book['_id']}",  # 👈 make each button unique
    on_click=log_download,
    kwargs={"book_id": str(book["_id"])}
)

        else:
            st.warning("No matching books found.")


def show_book_stats():
    st.subheader("📈 Popular Books Stats")
    books = list(books_meta.find().sort("downloads", -1).limit(10))
    if books:
        df = pd.DataFrame([{"Title": b["title"], "Downloads": b.get("downloads", 0)} for b in books])
        st.bar_chart(df.set_index("Title"))
    else:
        st.info("No download stats yet.")

def show_download_logs():
    st.subheader("📥 User Download Logs")
    logs = list(logs_col.find().sort("timestamp", -1).limit(100))
    if logs:
        data = []
        for log in logs:
            book = books_meta.find_one({"_id": log["book_id"]})
            data.append({
                "User": log["user"],
                "Book Title": book["title"] if book else "Unknown",
                "Timestamp": log["timestamp"].strftime("%Y-%m-%d %H:%M")
            })
        df = pd.DataFrame(data)
        st.dataframe(df)
        st.download_button("📄 Export Logs", df.to_csv(index=False), "download_logs.csv")
    else:
        st.info("No download logs found.")

def show_user_management():
    st.subheader("👥 User Management")
    users = list(users_col.find())
    for u in users:
        st.write(f"{u['username']} ({u['role']})")
    st.rerun()

def get_total_bookmarks():
    return sum([len(doc["book_ids"]) for doc in favorites_col.find() if "book_ids" in doc])

def show_bookmark_analytics():
    st.subheader("⭐ Most Bookmarked Books")
    all_favs = list(favorites_col.find())
    count_dict = {}
    for fav in all_favs:
        for bid in fav.get("book_ids", []):
            count_dict[bid] = count_dict.get(bid, 0) + 1

    if not count_dict:
        st.info("No bookmarks yet.")
        return

    stats = []
    for bid, count in count_dict.items():
        book = books_meta.find_one({"_id": bid})
        if book:
            stats.append({"Title": book["title"], "Bookmarks": count})

    df = pd.DataFrame(stats)
    st.bar_chart(df.set_index("Title"))
