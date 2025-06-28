import streamlit as st
from api import get_book, get_reviews
from utils import set_query_params, is_logged_in, get_user_id

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

    # if is_logged_in():
    #     user_id = get_user_id()
    #     rating = st.radio("Your Rating", [1, 2, 3, 4, 5], horizontal=True, key=f"rate_{book_id}")
    #     if st.button("Submit Rating"):
    #         res = requests.post(
    #             f"{API_BASE}/ratings",
    #             json={"user_id": user_id, "book_id": book_id, "rating": rating}
    #         )
    #         if res.status_code == 200:
    #             st.success("Rating saved!")
    #         else:
    #             st.error("Failed to save rating.")
    # else:
    #     st.info("Login to submit a rating.")
