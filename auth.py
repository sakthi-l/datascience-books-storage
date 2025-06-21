import bcrypt
from pymongo import MongoClient
import streamlit as st
import urllib.parse

# MongoDB connection using Streamlit secrets
username = st.secrets["mongodb"]["username"]
password = urllib.parse.quote_plus(st.secrets["mongodb"]["password"])
cluster = st.secrets["mongodb"]["cluster"]
appname = st.secrets["mongodb"]["appname"]

client = MongoClient(f"mongodb+srv://{username}:{password}@{cluster}/?retryWrites=true&w=majority&appName={appname}")
db = client["ebook_library"]
users_col = db["users"]

    

def register_user(username, password):
    if users_col.find_one({"username": username}):
        return False
    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    users_col.insert_one({"username": username, "password": hashed_pw, "role": "user"})
    return True

def login_user(username, password):
    user = users_col.find_one({"username": username})
    if user and bcrypt.checkpw(password.encode(), user["password"]):
        return True, user["role"]
    return False, None

def create_admin_if_not_exists():
    admin_user = st.secrets["admin"]["username"]
    admin_pass = st.secrets["admin"]["password"]

    existing = users_col.find_one({"username": admin_user})
    if not existing:
        users_col.insert_one({
            "username": admin_user,
            "password": admin_pass,
            "role": "admin"
        })
