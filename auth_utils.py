"Check password, hash, generate verification code. Static methods that we use a lot in our api service"

import random
import string
import bcrypt

class AuthUtils:
    # Passwords will be hashed
    @staticmethod
    def hash_password(password:str):
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed
    
    @staticmethod
    def check_password(password:str, hashed: bytes):
        return bcrypt.checkpw(password.encode('utf-8'), hashed)
    
    # Function to generate a 6-character verification code
    @staticmethod
    def generate_verification_code():
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))