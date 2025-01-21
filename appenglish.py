import os
import pandas as pd 
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from db_utils import DatabaseManager
import re

# Load environment variables
load_dotenv()

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = None

# Initialize database
db = DatabaseManager()

def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def validate_password(password: str) -> tuple[bool, str]:
    """
    Validate password strength.
    Returns: (is_valid, message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    return True, "Password is valid"

def login_page():
    """Display the login page."""
    st.title("Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")
        
        if submit_button:
            if username and password:
                success, message = db.verify_user(username, password)
                if success:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("Please fill in all fields")
    
    st.markdown("Don't have an account? [Create one](#register)")

def register_page():
    """Display the registration page."""
    st.title("Register")
    
    with st.form("register_form"):
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submit_button = st.form_submit_button("Register")
        
        if submit_button:
            if username and email and password and confirm_password:
                if not validate_email(email):
                    st.error("Please enter a valid email address")
                    return
                
                password_valid, password_message = validate_password(password)
                if not password_valid:
                    st.error(password_message)
                    return
                
                if password != confirm_password:
                    st.error("Passwords do not match")
                    return
                
                success, message = db.register_user(username, password, email)
                if success:
                    st.success(message)
                    st.info("Please go back to login page")
                else:
                    st.error(message)
            else:
                st.error("Please fill in all fields")

def logout():
    """Log out the user."""
    st.session_state['logged_in'] = False
    st.session_state['username'] = None
    st.rerun()

# Your existing FeedAnalyzer class here
# [Previous FeedAnalyzer code remains unchanged]

def main():
    """Main application function."""
    st.set_page_config(page_title="Feed Analyzer", page_icon="📊", layout="wide")
    
    # Add logout button if user is logged in
    if st.session_state['logged_in']:
        col1, col2 = st.columns([9, 1])
        with col2:
            if st.button("Logout"):
                logout()
    
    # Show appropriate page based on login state
    if not st.session_state['logged_in']:
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            login_page()
        with tab2:
            register_page()
            
    else:
        try:
            # Get API key from environment variable
            openai_api_key = os.environ.get("OPENAI_API_KEY")
            if not openai_api_key:
                st.error("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
                return
                
            st.title(f"📈 Feed Audit and Optimization - Welcome {st.session_state['username']}!")
            
            analyzer = FeedAnalyzer(openai_api_key)
            
            feed_file = st.file_uploader(
                "Select Excel feed file",
                type=["xlsx", "xls"]
            )
            
            if feed_file:
                url_to_analyze = st.text_input(
                    "URL to analyze",
                    placeholder="https://example.com"
                )
                
                if url_to_analyze:
                    if st.button("Start Analysis"):
                        with st.spinner("Analyzing feed..."):
                            try:
                                feed_data = analyzer.load_excel(feed_file)
                                results = analyzer.analyze_feed(feed_data, url_to_analyze)
                                
                                st.subheader("Analysis Results")
                                st.markdown(results)
                            except Exception as e:
                                st.error(f"Error during analysis: {str(e)}")
                        
        except Exception as e:
            st.error(f"Error initializing application: {str(e)}")

if __name__ == "__main__":
    main()
