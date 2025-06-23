import streamlit as st
import base64
import bcrypt
from pymongo import MongoClient
from datetime import datetime, time
import pandas as pd
import plotly.express as px
from bson import ObjectId
import socket
import gridfs

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
fs = gridfs.GridFS(db)

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
            st.rerun()  # ✅ use st.rerun for Streamlit ≥1.27
        else:
            user = users_col.find_one({"username": username})
            if user and user.get("verified") and bcrypt.checkpw(password.encode(), user["password"]):
                st.session_state["user"] = username
                st.success(f"Welcome {username}")
                st.rerun()
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
        keywords = st.text_input("Keywords (comma-separated)", key="upload_keywords")
        course_options = [
            "MAT445 - Probability & Statistics using R", "MAT446R01 - Mathematics for Data Science",
            "BIN522 - Python for Data Science", "INT413 - RDBMS, SQL & Visualization",
            "INT531 - Data Mining Techniques", "INT530R01 - Artificial Intelligence & Reasoning",
            "INT534R01 - Machine Learning", "CSE614R01 - Big Data Mining & Analytics",
            "INT418 - Predictive Analytics", "OEH014 - Ethics & Data Security",
            "INT419R01 - Applied Spatial Data Analytics Using R", "ICT601 - Machine Vision",
            "CSE615 - Deep Learning & Applications", "INT446 - Generative AI with LLMs",
            "CSE542 - Social Networks & Graph Analysis", "INT442 - Data Visualization Techniques",
            "INT424 - Algorithmic Trading", "INT426 - Bayesian Data Analysis",
            "BIN533R01 - Healthcare Data Analytics", "BIN529 - Data Science for Structural Biology",
            "Other / Not Mapped"
        ]
        course = st.selectbox("Course", course_options, key="upload_course")
        if st.button("Upload", key="upload_button"):
            data = uploaded_file.read()
            if len(data) == 0:
                st.error("File is empty")
                return
            data = uploaded_file.read()
            file_id = fs.put(data, filename=uploaded_file.name)
            
            books_col.insert_one({
                "title": title,
                "author": author,
                "language": language,
                "course": course,
                "keywords": [k.strip().lower() for k in keywords.split(",") if k.strip()],
                "file_id": file_id,
                "file_name": uploaded_file.name,
                "uploaded_at": datetime.utcnow()
            })
            st.success("Book uploaded")

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
        st.dataframe(df[['user', 'book', 'timestamp', 'type']])
    st.write("### 📚 Books Uploaded per Course")
    course_stats = books_col.aggregate([
        {"$group": {"_id": "$course", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ])
    course_data = [{"Course": row["_id"], "Count": row["count"]} for row in course_stats]
    if course_data:
        df = pd.DataFrame(course_data)
        st.dataframe(df)
        fig = px.bar(df, x="Course", y="Count", title="Books per Course")
        st.plotly_chart(fig)

# --- User Dashboard ---
def user_dashboard(user):
    st.subheader("📊 Your Dashboard")
    logs = list(logs_col.find({"user": user}))
    favs = list(fav_col.find({"user": user}))
    if logs:
        df = pd.DataFrame(logs)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        st.dataframe(df[['book', 'author', 'language', 'timestamp']])
    if favs:
        st.write("### ⭐ Bookmarked Books")
        book_ids = [ObjectId(f['book_id']) for f in favs]
        books = books_col.find({"_id": {"$in": book_ids}})
        for book in books:
            st.write(f"📘 {book['title']} by {book.get('author', 'Unknown')}")

def search_books():
    st.subheader("🔎 Search Books")

    with st.expander("🔧 Advanced Search Filters", expanded=True):
        title = st.text_input("Title", key="search_title")
        author = st.text_input("Author", key="search_author")
        keyword_input = st.text_input("Keywords (any match)", key="search_keywords")

        # Filter out empty values
        languages = [l for l in books_col.distinct("language") if l and l.strip()]
        courses = [c for c in books_col.distinct("course") if c and c.strip()]
        language_filter = st.selectbox("Filter by Language", ["All"] + sorted(languages), key="search_language")
        course_filter = st.selectbox("Filter by Course", ["All"] + sorted(courses), key="search_course")

        col1, col2 = st.columns(2)
        with col1:
            search_triggered = st.button("🔍 Search")
        with col2:
            if st.button("🔄 Clear Filters"):
                for key in ["search_title", "search_author", "search_language", "search_course", "search_keywords"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

    query = {}
    if title:
        query["title"] = {"$regex": title, "$options": "i"}
    if author:
        query["author"] = {"$regex": author, "$options": "i"}
    if keyword_input:
        keywords = [k.strip().lower() for k in keyword_input.split(",") if k.strip()]
        query["keywords"] = {"$in": keywords}
    if language_filter != "All":
        query["language"] = language_filter
    if course_filter != "All":
        query["course"] = course_filter

    if search_triggered:
        books = books_col.find(query)
    else:
        st.info("Showing latest 50 books. Use search filters to narrow down.")
        books = books_col.find().sort("uploaded_at", -1).limit(50)

    ip = get_ip()
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    guest_downloads_today = logs_col.count_documents({
        "user": "guest",
        "ip": ip,
        "type": "download",
        "timestamp": {"$gte": today_start}
    })

    for book in books:
        with st.expander(f"{book['title']}"):
            st.write(f"**Author:** {book.get('author', 'N/A')}")
            st.write(f"**Language:** {book.get('language', 'N/A')}")
            st.write(f"**Course:** {book.get('course', 'Not tagged')}")
            st.write(f"**Keywords:** {', '.join(book.get('keywords', []))}")

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

            if user == "admin":
                with st.expander("🛠️ Edit Metadata"):
                    new_title = st.text_input("Title", value=book["title"], key=f"et_{book['_id']}")
                    new_author = st.text_input("Author", value=book.get("author", ""), key=f"ea_{book['_id']}")
                    new_lang = st.text_input("Language", value=book.get("language", ""), key=f"el_{book['_id']}")
                    new_course = st.text_input("Course", value=book.get("course", ""), key=f"ec_{book['_id']}")
                    new_keywords = st.text_input("Keywords", value=", ".join(book.get("keywords", [])), key=f"ek_{book['_id']}")
                    if st.button("💾 Save Changes", key=f"save_{book['_id']}"):
                        books_col.update_one(
                            {"_id": book["_id"]},
                            {"$set": {
                                "title": new_title,
                                "author": new_author,
                                "language": new_lang,
                                "course": new_course,
                                "keywords": [k.strip().lower() for k in new_keywords.split(",") if k.strip()]
                            }}
                        )
                        st.success("Updated!")
                        st.rerun()

                if st.button("🗑️ Delete Book", key=f"del_{book['_id']}"):
                    fs.delete(book["file_id"])
                    books_col.delete_one({"_id": book["_id"]})
                    fav_col.delete_many({"book_id": str(book["_id"])})
                    logs_col.delete_many({"book": book["title"]})
                    st.warning("Deleted book")
                    st.rerun()

            elif can_download:
                try:
                    grid_file = fs.get(book["file_id"])
                    data = grid_file.read()
                    file_name = grid_file.filename

                    if st.download_button(
                        label="📄 Download Book",
                        data=data,
                        file_name=file_name,
                        mime="application/pdf",
                        key=f"dl_{book['_id']}"
                    ):
                        logs_col.insert_one({
                            "type": "download",
                            "user": user if user else "guest",
                            "ip": ip,
                            "book": book["title"],
                            "author": book.get("author"),
                            "language": book.get("language"),
                            "timestamp": datetime.utcnow()
                        })
                except Exception as e:
                    st.error(f"Could not retrieve file from storage: {e}")
            else:
                st.warning("Guests can download only 1 book per day. Please log in.")
def manage_users():
    st.subheader("👥 Manage Users")
    search_query = st.text_input("Search by username", key="search_user")
    query = {"username": {"$regex": search_query, "$options": "i"}} if search_query else {}
    users = list(users_col.find(query))

    if not users:
        st.info("No users found.")
        return

    for user in users:
        if st.button("❌ Delete User", key=f"delete_{user['_id']}"):
            confirm = st.checkbox(f"Confirm delete {user['username']}?", key=f"confirm_{user['_id']}")
        if confirm:
            users_col.delete_one({"_id": user["_id"]})
            logs_col.delete_many({"user": user["username"]})
            fav_col.delete_many({"user": user["username"]})
            st.warning("User deleted")
            st.rerun()
  # prevent modifying/deleting admin

        with st.expander(f"👤 {user['username']}"):
            st.write(f"✅ Verified: {'Yes' if user.get('verified') else 'No'}")
            st.write(f"🕒 Joined: {user.get('created_at', 'N/A')}")
            logs = list(logs_col.find({"user": user["username"]}).sort("timestamp", -1))
            favs = list(fav_col.find({"user": user["username"]}))

            if logs:
                st.write("📥 Downloads:")
                for l in logs[:5]:
                    st.write(f"- {l['book']} on {l['timestamp'].strftime('%Y-%m-%d')}")

            if favs:
                st.write("⭐ Favorites:")
                for f in favs:
                    book = books_col.find_one({"_id": ObjectId(f["book_id"])})
                    if book:
                        st.write(f"- {book['title']}")

            # User stats
            dl_count = logs_col.count_documents({"user": user["username"], "type": "download"})
            fav_count = fav_col.count_documents({"user": user["username"]})
            st.write(f"📥 Downloads: {dl_count}")
            st.write(f"⭐ Bookmarks: {fav_count}")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("✅ Toggle Verified", key=f"verify_{user['_id']}"):
                    users_col.update_one(
                        {"_id": user["_id"]},
                        {"$set": {"verified": not user.get("verified", False)}}
                    )
                    st.success("Verification status updated")
                    st.rerun()

            with col2:
                if st.button("❌ Delete User", key=f"delete_{user['_id']}"):
                    users_col.delete_one({"_id": user["_id"]})
                    logs_col.delete_many({"user": user["username"]})
                    fav_col.delete_many({"user": user["username"]})
                    st.warning("User deleted")
                    st.rerun()


def bulk_upload_with_gridfs():
    st.subheader("📥 Bulk Upload Books via CSV + PDF")

    st.markdown("""
    **CSV Format Required:**
    - `title`, `author`, `language`, `course`, `keywords`, `file_name`
    - PDFs must be uploaded alongside the CSV and match `file_name`
    """)

    csv_file = st.file_uploader("Upload Metadata CSV", type="csv", key="bulk_csv_gridfs")
    pdf_files = st.file_uploader("Upload PDF Files", type="pdf", accept_multiple_files=True, key="bulk_pdfs_gridfs")

    pdf_lookup = {f.name: f.read() for f in pdf_files} if pdf_files else {}

    if csv_file:
        df = pd.read_csv(csv_file)
        count = 0

        for _, row in df.iterrows():
            file_name = row.get("file_name")
            file_data = pdf_lookup.get(file_name)

            if not file_data:
                st.warning(f"Skipping '{row.get('title', 'Unknown')}' - no matching PDF file found.")
                continue

            file_id = fs.put(file_data, filename=file_name)

            books_col.insert_one({
                "title": row.get("title", ""),
                "author": row.get("author", ""),
                "language": row.get("language", ""),
                "course": row.get("course", ""),
                "keywords": [k.strip().lower() for k in str(row.get("keywords", "")).split(",")],
                "file_name": file_name,
                "file_id": file_id,
                "uploaded_at": datetime.utcnow()
            })
            count += 1

        st.success(f"{count} books uploaded successfully via GridFS!")


# --- Main ---
def main():
    st.set_page_config("📚 PDF Book Library")
    st.title("📚 PDF Book Library")

    # Always show search section
    search_books()
    st.markdown("---")

    # Login/Register
    if "user" not in st.session_state:
        choice = st.radio("Choose:", ["Login", "Register"])
        if choice == "Login":
            login_user()
        else:
            register_user()
        st.stop()  # ensure streamlit waits for rerun after login

    user = st.session_state["user"]
    st.success(f"Logged in as: {user}")

    if user == "admin":
        st.sidebar.markdown("## 🔐 Admin Controls")
        admin_tab = st.sidebar.radio("🛠️ Admin Panel", [
            "📤 Upload Book",
            "📥 Bulk Upload",
            "📊 Analytics",
            "👥 Manage Users"
        ])

        if admin_tab == "📤 Upload Book":
            upload_book()
        elif admin_tab == "📥 Bulk Upload":
            bulk_upload_with_gridfs()
        elif admin_tab == "📊 Analytics":
            admin_dashboard()
        elif admin_tab == "👥 Manage Users":
            manage_users()
    else:
        user_dashboard(user)

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()


if __name__ == "__main__":
    main()
