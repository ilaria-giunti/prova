import os
import pandas as pd
import streamlit as st
from langchain_openai.chat_models.base import BaseChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
import hashlib
import re
import json

# Load environment variables
load_dotenv()

# Authentication configuration
USERS_FILE = "users.json"
DEMO_PASSWORD = hashlib.sha256('demo123'.encode()).hexdigest()

class FeedAnalyzer:
    def __init__(self, deepseek_api_key: str):
        self.llm = BaseChatOpenAI(
            model='deepseek-chat',
            openai_api_key=os.environ.get("DEEPSEEK_API_KEY"),
            openai_api_base='https://api.deepseek.com',
            max_tokens=1024,
            temperature=0.2
        )

    @staticmethod
    def load_excel(file):
        try:
            df = pd.read_excel(file)
            if df.empty:
                raise ValueError("Excel file is empty")
            
            df.columns = df.columns.str.lower().str.strip()
            df.columns = df.columns.str.replace(' ', '_')
            
            column_mapping = {
                'name': 'title',
                'product_name': 'title',
                'desc': 'description',
                'category': 'google_product_category',
                'availability': 'availability',
                'price': 'price',
                'condition': 'condition',
                'custom_label': 'custom_label',
                'additional_images': 'additional_image_link'
            }
            
            return df.rename(columns=column_mapping)
        except Exception as e:
            raise Exception(f"Error loading Excel file: {e}")

    def get_optimization_advice(self, feed_data, url):
        examples_text = self._load_examples()
        
        fields = [
            'title', 'gtin', 'description', 'availability', 
            'google_product_category', 'custom_label', 
            'additional_image_link', 'price', 'condition', 'link'
        ]
        
        available_fields = [f for f in fields if f in feed_data.columns]
        feed_subset = feed_data[available_fields]

        prompt_template = """
        Analyze the following product feed using these reference examples:

        FEED DATA (first rows):
        {feed_data}

        MERCHANT URL: {url}

        REFERENCE EXAMPLES:
        {examples}

        Provide analysis and optimization suggestions for:
        1. Titles (brand positioning, length)
        2. Descriptions (structure, length)
        3. Images (quantity, quality)
        4. Custom labels (proper usage)
        5. Mandatory fields validation

        Include practical examples maintaining brand consistency.
        """
        
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["feed_data", "url", "examples"]
        )

        chain = LLMChain(llm=self.llm, prompt=prompt)
        
        return chain.run({
            "feed_data": feed_subset.head().to_string(),
            "url": url,
            "examples": examples_text
        })

    def _load_examples(self):
        try:
            examples_path = os.path.join("knowledge_base", "examples.txt")
            with open(examples_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            print(f"Error loading examples: {e}")
            return ""

# Authentication functions
def load_users():
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        users = {'demo': {'password': DEMO_PASSWORD, 'email': 'demo@example.com'}}
        save_users(users)
        return users

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

def validate_email(email: str) -> bool:
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email) is not None

def validate_password(password: str) -> tuple:
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not any(c.isupper() for c in password):
        return False, "Password must contain an uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain a lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain a number"
    return True, ""

def register_user(username: str, password: str, email: str) -> tuple:
    users = load_users()
    if username in users:
        return False, "Username already exists"
    if not validate_email(email):
        return False, "Invalid email format"
    
    password_valid, msg = validate_password(password)
    if not password_valid:
        return False, msg
    
    users[username] = {
        'password': hashlib.sha256(password.encode()).hexdigest(),
        'email': email
    }
    save_users(users)
    return True, "Registration successful"

def validate_login(username: str, password: str) -> tuple:
    users = load_users()
    if username not in users:
        return False, "Invalid credentials"
    if users[username]['password'] != hashlib.sha256(password.encode()).hexdigest():
        return False, "Invalid credentials"
    return True, ""

# UI Components
def login_form():
    with st.form("Login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            if username and password:
                success, message = validate_login(username, password)
                if success:
                    st.session_state.update(logged_in=True, username=username)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("Please fill all fields")

def registration_form():
    with st.form("Register"):
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        
        if st.form_submit_button("Register"):
            if password != confirm:
                st.error("Passwords don't match")
            else:
                success, message = register_user(username, password, email)
                if success:
                    st.success(message)
                else:
                    st.error(message)

def main_app():
    st.title(f"Feed Analyzer - Welcome {st.session_state.username}!")
    
    if st.button("Logout", key="logout"):
        st.session_state.clear()
        st.rerun()
    
    try:
        analyzer = FeedAnalyzer(os.environ.get("DEEPSEEK_API_KEY"))
        
        feed_file = st.file_uploader("Upload Excel Feed", type=["xlsx", "xls"])
        if feed_file:
            url = st.text_input("Merchant URL", placeholder="https://example.com")
            if url and st.button("Analyze"):
                with st.spinner("Analyzing..."):
                    try:
                        df = analyzer.load_excel(feed_file)
                        results = analyzer.get_optimization_advice(df, url)
                        st.subheader("Analysis Results")
                        st.markdown(results)
                    except Exception as e:
                        st.error(f"Analysis error: {str(e)}")
    except Exception as e:
        st.error(f"Initialization error: {str(e)}")

def main():
    st.set_page_config(page_title="Feed Analyzer", page_icon="📊", layout="wide")
    
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        st.title("Feed Analysis Platform")
        tab1, tab2 = st.tabs(["Login", "Register"])
        with tab1:
            login_form()
            st.info("Demo credentials: username='demo', password='demo123'")
        with tab2:
            registration_form()
    else:
        main_app()

if __name__ == "__main__":
    main()
