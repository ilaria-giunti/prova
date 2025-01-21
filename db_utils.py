import sqlite3
import bcrypt
from typing import Optional, Tuple
import os

class DatabaseManager:
    def __init__(self, db_name: str = "users.db"):
        self.db_name = db_name
        self._init_db()

    def _init_db(self):
        """Initialize the database and create tables if they don't exist."""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        # Create users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()

    def register_user(self, username: str, password: str, email: str) -> Tuple[bool, str]:
        """Register a new user."""
        try:
            # Hash the password
            salt = bcrypt.gensalt()
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
            
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            
            c.execute(
                'INSERT INTO users (username, password, email) VALUES (?, ?, ?)',
                (username, hashed_password, email)
            )
            
            conn.commit()
            conn.close()
            return True, "Registration successful!"
            
        except sqlite3.IntegrityError as e:
            error_message = str(e)
            if "username" in error_message:
                return False, "Username already exists!"
            elif "email" in error_message:
                return False, "Email already registered!"
            return False, "Registration failed!"
        except Exception as e:
            return False, f"An error occurred: {str(e)}"

    def verify_user(self, username: str, password: str) -> Tuple[bool, str]:
        """Verify user credentials."""
        try:
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            
            c.execute('SELECT password FROM users WHERE username = ?', (username,))
            result = c.fetchone()
            
            if result is None:
                return False, "Invalid username or password!"
            
            stored_password = result[0]
            
            if bcrypt.checkpw(password.encode('utf-8'), stored_password):
                return True, "Login successful!"
            
            return False, "Invalid username or password!"
            
        except Exception as e:
            return False, f"An error occurred: {str(e)}"
        finally:
            conn.close()

    def user_exists(self, username: str) -> bool:
        """Check if a username already exists."""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT 1 FROM users WHERE username = ?', (username,))
        exists = c.fetchone() is not None
        conn.close()
        return exists
