import bcrypt
from jose import jwt
from datetime import datetime, timedelta, timezone
from config import configs # Убрал get_auth_data, если он не нужен

# --- НОВЫЙ КОД ХЕШИРОВАНИЯ (БЕЗ passlib) ---

def get_password_hash(password: str) -> str:
    """Хеширование пароля с использованием bcrypt"""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    pwd_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    # checkpw сама безопасно сравнивает хеши
    return bcrypt.checkpw(pwd_bytes, hashed_bytes)

# --- JWT ОСТАЕТСЯ БЕЗ ИЗМЕНЕНИЙ ---

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=configs.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    encode_jwt = jwt.encode(to_encode, configs.SECRET_KEY, algorithm=configs.ALGORITHM)
    return encode_jwt

def decode_access_token(token: str):
    decode_jwt = jwt.decode(token, configs.SECRET_KEY, algorithms=[configs.ALGORITHM])
    return decode_jwt
