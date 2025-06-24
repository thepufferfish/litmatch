import streamlit as st
from api import get_books
from utils import get_query_param, set_query_params
from book_page import show_book_detail

st.set_page_config(page_title='Book Explorer', layout='wide')

# Sidebar
st.sidebar.title('📖 Browse Books')
# genre_filter = st.sidebar.selectbox('Filter by Genre', options=['All'] + ['Fiction', 'Nonfiction', 'Sci-Fi', 'Fantasy'])
search_query = st.sidebar.text_input('Search', '')

# Routing
book_id = st.query_params.get('book_id', None)
if book_id:
    show_book_detail(int(book_id))
    st.stop()

# Pagination
books = get_books()
# if genre_filter != 'All':
#     books = [b for b in books if b.get('genre') == genre_filter]
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
