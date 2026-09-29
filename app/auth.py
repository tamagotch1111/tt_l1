import hashlib
from fastapi import Request
from app.database import SessionLocal, User

def hash_password(password: str) -> str:
    # Надежное шифрование паролей
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def get_current_user(request: Request):
    # Достаем имя пользователя из куки браузера
    username = request.cookies.get("user_session")
    if not username:
        return None
    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    db.close()
    return user
