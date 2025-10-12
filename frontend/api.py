import streamlit as st
import requests

API_BASE = 'http://localhost:80'
TIMEOUT = 5

@st.cache_data
def get_genres():
    return requests.get(f'{API_BASE}/genres').json()

@st.cache_data
def get_books(genre: int = None):
    url = f'{API_BASE}/books'
    if genre:
        url += f'/?genre={genre}'
    return requests.get(url).json()

@st.cache_data
def get_book(book_id):
    # print(f'{API_BASE}/books/{book_id}')
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

def get_ratings(user_id: int | None, book_id: int | None):
    """ Gets ratings for a user and/or book """
    url = f'{API_BASE}/ratings/?'
    queries = []
    if user_id:
        queries.append(f'user_id={user_id}')
    if book_id:
        queries.append(f'book_id={book_id}')
    if len(queries) > 0:
        queries = '&'.join(queries)
        url += queries
    response = requests.get(url, timeout=TIMEOUT)
    if response.status_code == 200:
        return response.json()
    return None

def add_rating(user_id: int, book_id: int, rating: int):
    """ Adds or updates rating for a user and book """
    print({"user_id": user_id, "book_id": book_id, "rating": rating})
    response = requests.post(
        f"{API_BASE}/ratings",
        json={"user_id": user_id, "book_id": book_id, "rating": rating},
        timeout=TIMEOUT
    )
    if response.status_code == 200:
        st.success("Rating saved!")
        return response.json()
    st.error("Failed to save rating.")
    return None
