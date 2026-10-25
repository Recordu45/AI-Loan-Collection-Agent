from fastapi import Request, HTTPException
from passlib.context import CryptContext
from app.config import ADMIN_USERNAME, ADMIN_PASSWORD

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def authenticate(username: str, password: str):
    # Single configured admin for this starter. Use an organization IdP/MFA for production.
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return {"username": username, "role": "admin"}
    return None

def current_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Please log in")
    return user

def require_role(request: Request, allowed):
    user = current_user(request)
    if user.get("role") not in allowed:
        raise HTTPException(status_code=403, detail="Insufficient permission")
    return user
