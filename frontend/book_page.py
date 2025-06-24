import streamlit as st
from api import get_book, get_reviews
from utils import set_query_params

def show_book_detail(book_id):
    book = get_book(book_id)
    reviews = get_reviews(book_id)

    st.markdown(f'## {book['title']}')
    st.markdown(f'*by {book['author']}*')
    st.image(book['cover'], width=200)
    st.markdown(book.get('description', '_No description available._'))

    st.markdown('---')
    st.markdown('### 📝 Reviews')
    if reviews:
        for r in reviews:
            st.markdown(f'**{r['critic']}**')
            st.markdown(f'*{r['publication']}*')
            st.markdown(f'{'\u2b50'*int(r.get('rating', 0))}')
            st.markdown(f'{r['review']}')
            st.markdown(f'[Read full review]({r['url']})')
            st.markdown('---')
    else:
        st.markdown('_No reviews yet._')

    st.markdown('[\u2b05 Back to list](/)')
