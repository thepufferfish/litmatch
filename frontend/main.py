import streamlit as st
import requests

from api import get_books, login, register, get_genres, get_ratings, add_rating
from utils import (
    get_query_param, set_query_params, logout, is_logged_in, get_user_id,
)
from book_page import show_book_detail

st.set_page_config(page_title='Book Explorer', layout='wide')

# Sidebar
st.sidebar.title('📖 Browse Books')
genres = get_genres()
genre_filter = st.sidebar.selectbox('Filter by Genre', options=['All'] + [genre['name'] for genre in genres])
search_query = st.sidebar.text_input('Search', '')

st.sidebar.title("User Login")

if is_logged_in():
    st.sidebar.markdown(f"✅ Logged in as: **{st.session_state['user']['username']}**")
    if st.sidebar.button("Log out"):
        logout()
else:
    with st.sidebar.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            if not login(username, password):
                st.sidebar.error("Invalid credentials")

with st.sidebar.expander("Don't have an account? Register"):
    with st.form("register_form"):
        reg_username = st.text_input("New Username")
        reg_password = st.text_input("New Password", type="password")
        submitted = st.form_submit_button("Register")
        if submitted:
            if len(reg_password) < 6:
                st.warning("Password must be at least 6 characters.")
            else:
                register(reg_username, reg_password)

# Routing
book_id = st.query_params.get('book_id', None)
if book_id:
    show_book_detail(int(book_id))
    st.stop()

# Pagination
if genre_filter != 'All':
    genre = [genre['id'] for genre in genres if genre['name'] == genre_filter][0]
    books = get_books(genre=genre)
else:
    books = get_books()
if search_query:
    books = [b for b in books if search_query.lower() in b['title'].lower()]

page_size = 6
page = int(get_query_param('page') or 1)
start = (page - 1) * page_size
end = start + page_size

st.title('LitMatch')

for book in books[start:end]:
    cols = st.columns([1, 4])
    with cols[0]:
        st.image(book['cover'], use_container_width=True)
    with cols[1]:
        st.markdown(f'### [{book['title']}](?book_id={book['id']})')
        st.markdown(f'*by {book['author']}*')
        if is_logged_in():
            user_id = get_user_id()
            user_rating = get_ratings(user_id, book['id'])
            if user_rating:
                st.markdown(f'{'\u2b50'*int(user_rating[0].get('rating', 0))}')
            else:
                rating = st.radio("Your Rating", [1, 2, 3, 4, 5], horizontal=True, key=f"rate_{book['id']}")
                if st.button("Submit Rating", key=f"submit_rating_{book['id']}"):
                    user_rating = add_rating(user_id, book['id'], rating)

# Pagination controls
st.markdown('---')
col1, col2 = st.columns(2)
if page > 1:
    with col1:
        if st.button('⬅ Previous'):
            set_query_params(page=str(page - 1))
if end < len(books):
    with col2:
        if st.button('Next ➡'):
            set_query_params(page=str(page + 1))
