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
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables
load_dotenv()

class UserManager:
    def __init__(self):
        """Initialize Google Sheets API client."""
        try:
            # Create credentials from Streamlit secrets
            credentials_dict = st.secrets["gcp_service_account"]
            credentials = Credentials.from_service_account_info(
                credentials_dict,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            
            # Build the Sheets API service
            self.service = build('sheets', 'v4', credentials=credentials)
            self.spreadsheet_id = st.secrets["spreadsheet_id"]
            self.range_name = 'Users!A:D'  # Assuming sheet name is 'Users' and columns A-D
            
        except Exception as e:
            st.error(f"Failed to initialize Google Sheets API: {str(e)}")
            raise

    def get_users_df(self) -> pd.DataFrame:
        """Get users data from Google Sheets."""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=self.range_name
            ).execute()
            
            values = result.get('values', [])
            if not values:
                return pd.DataFrame(columns=['username', 'password_hash', 'email', 'created_at'])
            
            # Convert to DataFrame
            df = pd.DataFrame(values[1:], columns=values[0])  # First row as headers
            return df
            
        except Exception as e:
            st.error(f"Error reading from Google Sheets: {str(e)}")
            return pd.DataFrame(columns=['username', 'password_hash', 'email', 'created_at'])

    def hash_password(self, password: str) -> str:
        """Create a hash of the password."""
        return hashlib.sha256(password.encode()).hexdigest()

    def add_user_to_sheet(self, username: str, password_hash: str, email: str) -> bool:
        """Add a new user to the Google Sheet."""
        try:
            values = [
                [username, password_hash, email, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            ]
            
            body = {
                'values': values
            }
            
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=self.range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            return True
        except Exception as e:
            st.error(f"Error writing to Google Sheets: {str(e)}")
            return False

    def register_user(self, username: str, password: str, email: str) -> tuple[bool, str]:
        """Register a new user."""
        try:
            users_df = self.get_users_df()
            
            # Check if username exists
            if not users_df.empty and username in users_df['username'].values:
                return False, "Username already exists!"
            
            # Check if email exists
            if not users_df.empty and email in users_df['email'].values:
                return False, "Email already registered!"
            
            # Hash password
            password_hash = self.hash_password(password)
            
            # Add new user to sheet
            if self.add_user_to_sheet(username, password_hash, email):
                return True, "Registration successful!"
            else:
                return False, "Failed to register user"
            
        except Exception as e:
            return False, f"An error occurred: {str(e)}"

    def verify_user(self, username: str, password: str) -> tuple[bool, str]:
        """Verify user credentials."""
        try:
            users_df = self.get_users_df()
            
            if users_df.empty:
                return False, "Invalid username or password!"
            
            # Find user
            user = users_df[users_df['username'] == username]
            if user.empty:
                return False, "Invalid username or password!"
            
            # Verify password
            password_hash = self.hash_password(password)
            if password_hash != user.iloc[0]['password_hash']:
                return False, "Invalid username or password!"
            
            return True, "Login successful!"
            
        except Exception as e:
            return False, f"An error occurred: {str(e)}"
