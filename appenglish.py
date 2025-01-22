import os
import pandas as pd 
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import hashlib
import re
from datetime import datetime
import json

# Load environment variables
load_dotenv()

# File to store users (simulating a database)
USERS_FILE = "users.json"

def load_users():
    """Load users from JSON file."""
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Initialize with demo user if file doesn't exist
        users = {
            'demo': {
                'password': hashlib.sha256('demo123'.encode()).hexdigest(),
                'email': 'demo@example.com'
            }
        }
        save_users(users)
        return users

def save_users(users):
    """Save users to JSON file."""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

class FeedAnalyzer:
    def __init__(self, openai_api_key: str = None):
        """Initialize the analyzer with OpenAI API key."""
        self.api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY must be provided either as parameter or environment variable")
            
        self.llm = ChatOpenAI(
            api_key=self.api_key,
            temperature=0.2,
            model="gpt-3.5-turbo"
        )

    @staticmethod
    def load_excel(file):
        """Load and process Excel file."""
        try:
            df = pd.read_excel(file)
            if df.empty:
                raise ValueError("The Excel file is empty")
            
            df.columns = df.columns.str.lower().str.strip()
            
            column_mapping = {
                'title': 'title',
                'description': 'description',
                'price': 'price',
                'availability': 'availability',
                'additional_images': 'additional_image_link'
            }
            
            return df.rename(columns=column_mapping)
        except Exception as e:
            raise Exception(f"Error loading Excel file: {e}")

    def check_prices(self, url):
        """Check prices from the website."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            price = soup.find('span', class_='price')
            sale_price = soup.find('span', class_='sale-price')
            
            return {
                'price': price.text.strip() if price else None,
                'sale_price': sale_price.text.strip() if sale_price else None
            }
        except Exception as e:
            print(f"Error scraping prices: {e}")
            return None

    def analyze_feed(self, feed_data, merchant_url):
        """Analyze the feed data."""
        try:
            sample_data = feed_data.sample(n=3) if len(feed_data) > 3 else feed_data
            
            price_check = None
            if 'link' in sample_data.columns:
                sample_url = sample_data['link'].iloc[0]
                price_check = self.check_prices(sample_url)

            prompt = PromptTemplate(
                template=self.get_analysis_prompt(),
                input_variables=["feed_data", "url", "price_analysis"]
            )

            chain = LLMChain(llm=self.llm, prompt=prompt)
            
            result = chain.run({
                "feed_data": sample_data.to_string(),
                "url": merchant_url,
                "price_analysis": str(price_check) if price_check else "No price analysis available"
            })
            
            return result
        except Exception as e:
            raise Exception(f"Error analyzing feed: {e}")

    @staticmethod
    def get_analysis_prompt():
        """Get the analysis prompt template."""
        return '''
        You are an expert in Google Merchant Center. Analyze the feed and provide a structured output as follows:

        1. TITLES
        -Evaluate the titles
        If you find issues, such as titles exceeding 150 characters or missing brand name, flag them, otherwise skip.
        -Provide optimized title examples as follows:

        For each title that needs optimization, directly provide the example:
        OPTIMIZED TITLE: [new title]

        2. IMAGES (only if necessary)
        - Flag if additional_image_link is missing, otherwise skip.
        - Flag if there are fewer than 2 images between image_link and additional_image_link

        3. PRICE (only if necessary):
        - Flag if the price doesn't match the website price

        4. DESCRIPTIONS:
        - Evaluate the descriptions and provide optimized examples:
        OPTIMIZED DESCRIPTION: [new description]

        5. MISSING REQUIRED FIELDS
        If there are missing required fields for any product, indicate:
        Product name: missing attribute
        - id
        - title 
        - description
        - link
        - image_link
        - availability
        - price
        - google_product_category
        - brand
        - condition
        [list only those actually missing]

        Feed to analyze:
        {feed_data}

        URL: {url}

        Price analysis:
        {price_analysis}

        IMPORTANT: 
        - For each title to optimize, always show before and after
        - For each product with missing fields, list only the fields that are actually missing
        - Flag ONLY the problems found. If something is correct, don't mention it
        '''

def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def validate_password(password: str) -> tuple[bool, str]:
    """Validate password strength."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    return True, "Password is valid"

def register_user(username: str, password: str, email: str) -> tuple[bool, str]:
    """Register a new user."""
    users = load_users()
    
    if username in users:
        return False, "Username already exists!"
    
    # Hash password
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    # Add new user
    users[username] = {
        'password': password_hash,
        'email': email
    }
    
    # Save updated users
    save_users(users)
    return True, "Registration successful!"

def validate_user(username: str, password: str) -> tuple[bool, str]:
    """Validate user credentials."""
    users = load_users()
    
    if username not in users:
        return False, "Invalid username or password!"
        
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if password_hash != users[username]['password']:
        return False, "Invalid username or password!"
        
    return True, "Login successful!"

def login_page():
    """Display the login page."""
    st.title("Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        st.info("Demo credentials - Username: demo, Password: demo123")
        submit_button = st.form_submit_button("Login")
        
        if submit_button:
            if username and password:
                success, message = validate_user(username, password)
                if success:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("Please fill in all fields")

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
                
                success, message = register_user(username, password, email)
                if success:
                    st.success(message)
                    st.info("You can now login with your credentials")
                else:
                    st.error(message)
            else:
                st.error("Please fill in all fields")

def main():
    """Main application function."""
    st.set_page_config(page_title="Feed Analyzer", page_icon="📊", layout="wide")
    
    # Initialize session state
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
    if 'username' not in st.session_state:
        st.session_state['username'] = None
    
    # Add logout button if user is logged in
    if st.session_state['logged_in']:
        col1, col2 = st.columns([9, 1])
        with col2:
            if st.button("Logout"):
                st.session_state['logged_in'] = False
                st.session_state['username'] = None
                st.rerun()
    
    # Show appropriate page based on login state
    if not st.session_state['logged_in']:
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            login_page()
        with tab2:
            register_page()
    else:
        try:
            # Get API key
            openai_api_key = st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
            if not openai_api_key:
                st.error("OpenAI API key not found. Please set it in Streamlit secrets or environment variables.")
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
