import streamlit as st

def set_query_params(**params):
    st.query_params.from_dict(dict(**params))

def get_query_param(name):
    return st.query_params.get(name, [None])[0]