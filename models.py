"Pydantic models"

from pydantic import BaseModel, Field

# These classes are used to ensure that the contents of the incoming API request for login and registration is in the desired format.
class RegisterUser(BaseModel):
    email: str = Field(..., max_length=200, pattern=r'^\S+@\S+\.\S+$')
    password: str = Field(..., max_length=64)
    api_key: str = Field(..., max_length=32)

class LoginUser(BaseModel):
    email: str
    password: str
    
class ChangeAPIKey(BaseModel):
    email: str = Field(..., max_length=32, pattern="^[a-zA-Z0-9]*$")
    # old_api_key: str = Field(..., max_length=32)
    new_api_key: str = Field(..., max_length=32)

class ChangePassword(BaseModel):
    email: str = Field(..., max_length=32, pattern="^[a-zA-Z0-9]*$")
    old_password: str = Field(..., max_length=64)
    new_password: str = Field(..., max_length=64)
    
class VerifyEmailCode(BaseModel):
    email: str = Field(..., max_length=200)
    verification_code: str = Field(..., max_length=6)