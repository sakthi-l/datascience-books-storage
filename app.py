import streamlit as st
import base64
import bcrypt
import urllib.parse
from pymongo import MongoClient
from datetime import datetime
import pandas as pd
import fitz  # PyMuPDF for PDF previews
import plotly.express as px
from bson import ObjectId

# --- Secrets and MongoDB Setup ---
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

# --- Theme Toggle ---
def set_theme():
    theme = st.radio("Select Theme", ["Light", "Dark"], horizontal=True, key="theme_toggle")
    if theme == "Dark":
        st.markdown("""<style>
            .stApp { background-color: #0E1117; color: white; }
            div[data-testid="stSidebar"] { background-color: #161A23; }
            h1, h2, h3, h4, h5, h6, .css-10trblm, .css-1v3fvcr { color: white !important; }
            input, textarea, .stButton > button { background-color: #2c2f38; color: white; border-color: #444; }
            .stTextInput > div > div > input { background-color: #2c2f38; color: white; }
        </style>""", unsafe_allow_html=True)
    else:
        st.markdown("""<style>
            .stApp { background-color: white; color: black; }
            div[data-testid="stSidebar"] { background-color: #F0F2F6; }
            h1, h2, h3, h4, h5, h6, .css-10trblm, .css-1v3fvcr { color: black !important; }
            input, textarea, .stButton > button { background-color: white; color: black; border-color: #ccc; }
            .stTextInput > div > div > input { background-color: white; color: black; }
        </style>""", unsafe_allow_html=True)

# --- Registration ---
def register_user():
    st.markdown('<h3 style="font-size:24px;">📝 Register</h3>', unsafe_allow_html=True)
    username = st.text_input("Choose a username", key="reg_username")
    password = st.text_input("Choose a password", type="password", key="reg_password")
    if st.button("Register", key="reg_button"):
        if users_col.find_one({"username": username}):
            st.error("❌ Username already exists!")
        else:
            hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            users_col.insert_one({
                "username": username,
                "password": hashed_pw,
                "verified": True,
                "created_at": datetime.utcnow()
            })
            st.success("✅ Registered successfully! You can now log in.")

# --- Login ---
def login_user():
    st.markdown('<h3 style="font-size:24px;">🔐 Login</h3>', unsafe_allow_html=True)
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Login", key="login_button"):
        if username == admin_user and password == admin_pass:
            st.session_state["user"] = "admin"
            st.success("🛡️ Logged in as Admin")
        else:
            user = users_col.find_one({"username": username})
            if user and user.get("verified") and bcrypt.checkpw(password.encode(), user["password"]):
                st.session_state["user"] = username
                st.success(f"✅ Welcome {username}")
            else:
                st.error("❌ Invalid or unverified credentials!")

# --- Upload Book ---
def upload_book():
    st.markdown('<h3 style="font-size:24px;">📄 Upload Book (Admin Only)</h3>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload PDF", type="pdf", key="pdf_uploader")
    title = st.text_input("Title", key="upload_title")
    author = st.text_input("Author", key="upload_author")
    keywords = st.text_input("Keywords (comma separated)", key="upload_keywords")
    domain = st.text_input("Domain", key="upload_domain")
    isbn = st.text_input("ISBN", key="upload_isbn")
    language = st.text_input("Language", key="upload_language")
    year = st.text_input("Published Year", key="upload_year")

    if uploaded_file and st.button("Upload", key="upload_button"):
        data = uploaded_file.read()
        preview = ""
        try:
            with fitz.open(stream=data, filetype="pdf") as doc:
                preview = doc[0].get_text()
        except: pass
        encoded = base64.b64encode(data).decode()
        book = {
            "title": title,
            "author": author,
            "keywords": [k.strip() for k in keywords.split(",")],
            "domain": domain,
            "isbn": isbn,
            "language": language,
            "published_year": year,
