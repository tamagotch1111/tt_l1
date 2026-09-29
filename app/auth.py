import hashlib
from fastapi import Request
from app.database import SessionLocal, User

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def get_current_user(request: Request):
    session_username = request.cookies.get("user_session")
    if not session_username:
        return None
    db = SessionLocal()
    user = db.query(User).filter(User.username == session_username).first()
    db.close()
    if not user or not getattr(user, "is_active", True):
        return None
    return user
