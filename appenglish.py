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
REQUIRED_FIELDS = ['id', 'title', 'description', 'link', 'image_link', 'availability', 'price', 'condition']

class FeedAnalyzer:
    def __init__(self, deepseek_api_key: str):
        self.llm = BaseChatOpenAI(
            model='deepseek-chat',
            openai_api_key=os.environ.get("DEEPSEEK_API_KEY"),
            openai_api_base='https://api.deepseek.com',
            max_tokens=2048,
            temperature=0.1
        )

    @staticmethod
    def load_excel(file):
        try:
            df = pd.read_excel(file)
            if df.empty:
                raise ValueError("Excel file is empty")
            
            # Normalization pipeline
            df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')
            
            column_mapping = {
                'name': 'title',
                'product_name': 'title',
                'desc': 'description',
                'category': 'google_product_category',
                'availability': 'availability',
                'price': 'price',
                'condition': 'condition',
                'custom_label': 'custom_label',
                'additional_images': 'additional_image_link',
                'product_url': 'link'
            }
            
            return df.rename(columns=column_mapping)
            
        except Exception as e:
            raise Exception(f"Error loading Excel file: {e}")

    def get_optimization_advice(self, feed_data, url):
        examples_text = self._load_examples()
        validation_results = self._validate_structure(feed_data)
        
        # Smart sampling
        analysis_sample = self._get_analysis_sample(feed_data)
        
        prompt_template = """Analyze this product feed following Google Merchant Center guidelines:

FEED SAMPLE (representative products):
{feed_data}

MERCHANT URL: {url}

REFERENCE EXAMPLES:
{examples}

MANDATORY FIELD CHECK:
{validation}

STRUCTURED ANALYSIS REQUIRED:
1. TITLES ANALYSIS:
- Verify brand positioning (Faan Fruit first)
- Check length <=150 chars
- Flag invalid titles with [BAD]
- Provide 3 optimized examples with [OPTIMIZED]

2. DESCRIPTIONS ANALYSIS: 
- Check length <=5000 chars
- Flag SEO issues with [ISSUE]
- Provide 2 optimized examples with [OPTIMIZED]

3. IMAGE ANALYSIS:
- Verify additional_image_link presence
- Count total images per product
- Flag products with <3 images with [WARNING]

4. CUSTOM LABELS:
- Validate proper usage
- Suggest values based on product type

5. CRITICAL ISSUES:
- List missing mandatory fields
- Highlight pricing mismatches
- Identify invalid URLs

RESPONSE FORMAT:
### [Section Name]
- [Finding 1]
- [Finding 2]
[Optimized Example 1]
[Optimized Example 2]

RULES:
1. Only mention problematic fields
2. Use exact field names from feed
3. Skip sections with no issues
4. Prioritize critical errors first"""
        
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["feed_data", "url", "examples", "validation"]
        )

        chain = LLMChain(llm=self.llm, prompt=prompt)
        
        return chain.run({
            "feed_data": analysis_sample.to_string(),
            "url": url,
            "examples": examples_text,
            "validation": validation_results
        })

    def _load_examples(self):
        try:
            with open(os.path.join("knowledge_base", "examples.txt"), 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            print(f"Example loading error: {e}")
            return "No reference examples available"

    def _validate_structure(self, df):
        missing_fields = [f for f in REQUIRED_FIELDS if f not in df.columns]
        return f"Missing mandatory fields: {', '.join(missing_fields)}" if missing_fields else "All mandatory fields present"

    def _get_analysis_sample(self, df):
        return df.sample(n=5) if len(df) > 5 else df

# Authentication functions (unchanged but included for completeness)
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
        
        with st.form("analysis_form"):
            feed_file = st.file_uploader("Upload Excel Feed", type=["xlsx", "xls"])
            url = st.text_input("Merchant URL", placeholder="https://example.com")
            
            if st.form_submit_button("Analyze") and feed_file and url:
                with st.spinner("Analyzing..."):
                    try:
                        df = analyzer.load_excel(feed_file)
                        results = analyzer.get_optimization_advice(df, url)
                        
                        st.subheader("Analysis Results")
                        st.markdown(results)
                        
                        # Show raw data preview
                        with st.expander("Data Preview"):
                            st.dataframe(df.head(3))
                            
                    except Exception as e:
                        st.error(f"Analysis error: {str(e)}")

    except Exception as e:
        st.error(f"Initialization error: {str(e)}")

def main():
    st.set_page_config(page_title="Feed Analyzer Pro", page_icon="📊", layout="wide")
    
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
