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
