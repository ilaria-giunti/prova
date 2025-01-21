import os
import pandas as pd 
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import bcrypt
from typing import Tuple
import pymongo
from datetime import datetime
import re

# Load environment variables
load_dotenv()

# Initialize MongoDB connection
class DatabaseManager:
    def __init__(self):
        # Get MongoDB connection string from environment variable or Streamlit secrets
        mongo_uri = st.secrets.get("MONGO_URI") or os.environ.get("MONGO_URI")
        if not mongo_uri:
            raise ValueError("MongoDB connection string not found in environment variables or secrets")
            
        self.client = pymongo.MongoClient(mongo_uri)
        self.db = self.client.feed_analyzer
        self.users = self.db.users
        
        # Create indexes
        self.users.create_index("username", unique=True)
        self.users.create_index("email", unique=True)

    def register_user(self, username: str, password: str, email: str) -> Tuple[bool, str]:
        """Register a new user."""
        try:
            # Hash the password
            salt = bcrypt.gensalt()
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
            
            # Create user document
            user_doc = {
                "username": username,
                "password": hashed_password,
                "email": email,
                "created_at": datetime.utcnow()
            }
            
            # Insert the user
            self.users.insert_one(user_doc)
            return True, "Registration successful!"
            
        except pymongo.errors.DuplicateKeyError as e:
            if "username" in str(e):
                return False, "Username already exists!"
            elif "email" in str(e):
                return False, "Email already registered!"
            return False, "Registration failed!"
        except Exception as e:
            return False, f"An error occurred: {str(e)}"

    def verify_user(self, username: str, password: str) -> Tuple[bool, str]:
        """Verify user credentials."""
        try:
            user = self.users.find_one({"username": username})
            
            if user is None:
                return False, "Invalid username or password!"
            
            stored_password = user["password"]
            
            if bcrypt.checkpw(password.encode('utf-8'), stored_password):
                return True, "Login successful!"
            
            return False, "Invalid username or password!"
            
        except Exception as e:
            return False, f"An error occurred: {str(e)}"

    def user_exists(self, username: str) -> bool:
        """Check if a username already exists."""
        return self.users.find_one({"username": username}) is not None

    def close(self):
        """Close the database connection."""
        self.client.close()

class FeedAnalyzer:
    def __init__(self, openai_api_key: str = None):
        """Initialize the analyzer with OpenAI API key."""
        # First try the passed key, then environment variable
        self.api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY must be provided either as parameter or environment variable")
            
        self.llm = ChatOpenAI(
            api_key=self.api_key,
            temperature=0.2,
            model="gpt-4"
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

    def load_examples(self):
        """Load example data from knowledge base."""
        try:
            examples_path = os.path.join("knowledge_base", "examples.txt")
            with open(examples_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            examples = []
            for example in content.split('EXAMPLE ')[1:]:
                example_dict = {}
                lines = example.strip().split('\n')
                
                for line in lines:
                    if line.startswith('URL:'):
                        example_dict['url'] = line.replace('URL:', '').strip()
                    elif line.startswith('TITLE:'):
                        example_dict['title'] = line.replace('TITLE:', '').strip()
                    elif line.startswith('DESCRIPTION:'):
                        example_dict['description'] = line.replace('DESCRIPTION:', '').strip()
                    elif line.startswith('CUSTOM_LABEL_0:'):
                        example_dict['custom_label_0'] = line.replace('CUSTOM_LABEL_0:', '').strip()
                    elif line.startswith('CUSTOM_LABEL_1:'):
                        example_dict['custom_label_1'] = line.replace('CUSTOM_LABEL_1:', '').strip()
                
                if example_dict:
                    examples.append(example_dict)
            
            return examples
        except Exception as e:
            print(f"Error loading examples: {e}")
            return []

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
            examples = self.load_examples()
            examples_text = self.format_examples(examples)
            
            price_check = None
            if 'link' in sample_data.columns:
                sample_url = sample_data['link'].iloc[0]
                price_check = self.check_prices(sample_url)

            prompt = PromptTemplate(
                template=self.get_analysis_prompt(),
                input_variables=["feed_data", "url", "examples", "price_analysis"]
            )

            chain = LLMChain(llm=self.llm, prompt=prompt)
            
            result = chain.run({
                "feed_data": sample_data.to_string(),
                "url": merchant_url,
                "examples": examples_text,
                "price_analysis": str(price_check) if price_check else "No price analysis available"
            })
            
            return result
        except Exception as e:
            raise Exception(f"Error analyzing feed: {e}")

    @staticmethod
    def format_examples(examples):
        """Format examples for the prompt."""
        examples_text = ""
        for i, example in enumerate(examples, 1):
            examples_text += f"\nEXAMPLE {i}:\n"
            examples_text += f"URL: {example.get('url', '')}\n"
            examples_text += f"TITLE: {example.get('title', '')}\n"
            examples_text += f"CUSTOM_LABEL_0: {example.get('custom_label_0', '')}\n"
            examples_text += f"CUSTOM_LABEL_1: {example.get('custom_label_1', '')}\n"
        return examples_text

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

        5. CUSTOM LABELS
        If not present, provide custom_label examples that could be useful for each product:
        PRODUCT: [name]
        - Custom Label 0: [specific suggestion for that product]
        - Custom Label 1: [specific suggestion for that product]
        - Custom Label 2: [specific suggestion for that product]

        6. MISSING REQUIRED FIELDS
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

        Reference examples:
        {examples}

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

def login_page():
    """Display the login page."""
    st.title("Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")
        
        if submit_button:
            if username and password:
                db = DatabaseManager()
                success, message = db.verify_user(username, password)
                if success:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
                db.close()
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
                
                db = DatabaseManager()
                success, message = db.register_user(username, password, email)
                if success:
                    st.success(message)
                    st.info("Please go back to login page")
                else:
                    st.error(message)
                db.close()
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
                
                if Fixed section of appenglish.py

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

if __name__ == "__main__":
    main()
