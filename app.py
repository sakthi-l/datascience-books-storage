import streamlit.components.v1 as components
import tempfile
import base64

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

            # 👁️ View PDF (works for all)
            if st.button(f"📖 View PDF – {book['file_name']}", key=f"view_{book['_id']}"):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(base64.b64decode(book["file_base64"]))
                    tmp_file_path = tmp_file.name
                with open(tmp_file_path, "rb") as f:
                    base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                    pdf_display = f'<embed src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800px" type="application/pdf">'
                    st.markdown(pdf_display, unsafe_allow_html=True)

            # 🔐 Download and Bookmark only if logged in
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
