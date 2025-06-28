import streamlit as st
import requests

API_BASE = 'http://localhost:80'

@st.cache_data
def get_books():
    return requests.get(f'{API_BASE}/books').json()

@st.cache_data
def get_book(book_id):
    print(f'{API_BASE}/books/{book_id}')
    return requests.get(f'{API_BASE}/books/{book_id}').json()

@st.cache_data
def get_reviews(book_id):
    return requests.get(f'{API_BASE}/reviews/{book_id}').json()

def login(username, password):
    response = requests.post(f"{API_BASE}/auth/login", json={"username": username, "password": password})
    if response.status_code == 200:
        st.session_state["user"] = response.json()
        return True
    else:
        return False

def register(username, password):
    response = requests.post(f"{API_BASE}/auth/register", json={
        "username": username,
        "password": password
    })
    if response.status_code == 200:
        st.success("Registration successful. You can now log in.")
    elif response.status_code == 400:
        st.error("Username already exists.")
    else:
        st.error("Registration failed.")
    st.session_state["user"] = response.json()
    return True