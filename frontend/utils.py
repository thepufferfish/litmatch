import streamlit as st
import requests

def set_query_params(**params):
    st.query_params.from_dict(dict(**params))

def get_query_param(name):
    return st.query_params.get(name, [None])[0]

def is_logged_in():
    return "user" in st.session_state

def get_user_id():
    return st.session_state.get("user", {}).get("id")

def logout():
    st.session_state.pop("user", None)
