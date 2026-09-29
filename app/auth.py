from fastapi import Request
from passlib.context import CryptContext
from app.database import SessionLocal, User

# Используем bcrypt для стойкого криптографического хеширования
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def get_current_user(request: Request):
    username = request.cookies.get("user_session")
    if not username:
        return None
    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    db.close()
    return user
