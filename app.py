import streamlit as st
from pymongo import MongoClient
import base64


db_password = st.secrets["mongodb"]["db_password"]
srv_link = f"mongodb+srv://DATASCIENCE-BOOKS:{db_password}@books.rvarfaj.mongodb.net/?retryWrites=true&w=majority&appName=BOOKS"
client = MongoClient(srv_link)
db = client["library"]
collection = db["books"]

def show_pdf(file_base64, file_name):
    b64 = file_base64
    pdf_display = f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600px"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

def upload_book():
    st.subheader("📤 Upload New Book")
    uploaded_file = st.file_uploader("Choose a PDF", type="pdf")
    title = st.text_input("Title")
    author = st.text_input("Author")
    course = st.selectbox("Course", [
        "MAT445 – Probability & Statistics using R",
        "DS101 – Data Science Basics",
        "CS501 – Machine Learning",
        "Other"
    ])
    isbn = st.text_input("ISBN")
    language = st.text_input("Language")
    published_year = st.text_input("Published Year")

    if uploaded_file and st.button("Upload Book"):
        file_data = uploaded_file.read()
        file_b64 = base64.b64encode(file_data).decode()
        book_data = {
            "title": title.strip(),
            "author": author.strip(),
            "course": course,
            "isbn": isbn.strip(),
            "language": language.strip(),
            "published_year": published_year.strip(),
            "file_base64": file_b64,
            "file_name": uploaded_file.name
        }
        st.write("🔍 Saving to MongoDB:", book_data)  # debug print
        collection.insert_one(book_data)
        st.success(f"✅ '{title}' uploaded!")

def search_and_display_books():
    st.subheader("🔍 Search Books")
    title = st.text_input("Title")
    author = st.text_input("Author")
    course = st.selectbox("Course", ["", "MAT445 – Probability & Statistics using R", "DS101 – Data Science Basics", "CS501 – Machine Learning", "Other"])
    isbn = st.text_input("ISBN")
    language = st.text_input("Language")
    published_year = st.text_input("Published Year")

    query = {}
    if title: query["title"] = {"$regex": title, "$options": "i"}
    if author: query["author"] = {"$regex": author, "$options": "i"}
    if course: query["course"] = course
    if isbn: query["isbn"] = {"$regex": isbn, "$options": "i"}
    if language: query["language"] = {"$regex": language, "$options": "i"}
    if published_year: query["published_year"] = {"$regex": published_year, "$options": "i"}

    st.write("🔍 Running query:", query)  # debug print
    books = list(collection.find(query))

    if books:
        for book in books:
            with st.expander(book["title"]):
                st.write(f"**Author:** {book.get('author','-')}")
                st.write(f"**Course:** {book.get('course','-')}")
                st.write(f"**ISBN:** {book.get('isbn','-')}")
                st.write(f"**Language:** {book.get('language','-')}")
                st.write(f"**Year:** {book.get('published_year','-')}")
                if st.button(f"📥 Download {book['file_name']}", key=str(book['_id'])):
                    href = f'<a href="data:application/pdf;base64,{book["file_base64"]}" download="{book["file_name"]}">Download PDF</a>'
                    st.markdown(href, unsafe_allow_html=True)
    else:
        st.info("No matching books found.")


def main():
    st.set_page_config("📚 Data Science Book Library")
    st.title("📚 Data Science Book Library")

    search_and_display_books()
    
    st.markdown("---")
    upload_book()

if __name__ == "__main__":
    main()
