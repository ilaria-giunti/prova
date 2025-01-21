class UserManager:
    def __init__(self):
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
            self.range_name = 'Users!A:D'  # A: username, B: password_hash, C: email, D: created_at
            
        except Exception as e:
            st.error(f"Failed to initialize Google Sheets API: {str(e)}")
            raise

    def get_users(self):
        """Get users data from Google Sheets."""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=self.range_name
            ).execute()
            
            values = result.get('values', [])
            if not values:
                return {}
            
            # Convert to dictionary for easier lookup
            users = {}
            headers = values[0]
            for row in values[1:]:  # Skip header row
                user_data = dict(zip(headers, row))
                users[user_data['username']] = {
                    'password': user_data['password_hash'],
                    'email': user_data['email'],
                    'created_at': user_data.get('created_at', '')
                }
            return users
            
        except Exception as e:
            st.error(f"Error reading from Google Sheets: {str(e)}")
            return {}

    def add_user(self, username: str, password_hash: str, email: str) -> bool:
        """Add a new user to Google Sheets."""
        try:
            # Prepare new user data
            new_user = [
                [username, password_hash, email, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            ]
            
            body = {
                'values': new_user,
                'majorDimension': 'ROWS'
            }
            
            # Append the new user to the sheet
            request = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=self.range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            )
            
            response = request.execute()
            return 'updates' in response
            
        except Exception as e:
            st.error(f"Error writing to Google Sheets: {str(e)}")
            return False

    def register_user(self, username: str, password: str, email: str) -> tuple[bool, str]:
        """Register a new user."""
        try:
            # Get current users
            users = self.get_users()
            
            # Check if username exists
            if username in users:
                return False, "Username already exists!"
            
            # Check if email exists
            if any(user['email'] == email for user in users.values()):
                return False, "Email already registered!"
            
            # Hash password
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            # Add new user to sheet
            if self.add_user(username, password_hash, email):
                return True, "Registration successful!"
            else:
                return False, "Failed to register user"
            
        except Exception as e:
            return False, f"An error occurred: {str(e)}"

    def verify_user(self, username: str, password: str) -> tuple[bool, str]:
        """Verify user credentials."""
        try:
            users = self.get_users()
            
            if username not in users:
                return False, "Invalid username or password!"
            
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if password_hash != users[username]['password']:
                return False, "Invalid username or password!"
            
            return True, "Login successful!"
            
        except Exception as e:
            return False, f"An error occurred: {str(e)}"
