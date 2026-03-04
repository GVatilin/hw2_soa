from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt, JWTError
from generated.models.error_code import ErrorCode

from .settings import settings
from .errors import ApiError

ALGO = "HS256"


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode("utf-8"), h.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: str, role: str) -> tuple[str, int]:
    exp = datetime.now() + timedelta(minutes=settings.access_ttl_min)
    token = jwt.encode({"sub": user_id, "role": role, "type": "access", "exp": exp}, settings.jwt_secret, algorithm=ALGO)
    return token, int(settings.access_ttl_min * 60)


def create_refresh_token(user_id: str, role: str) -> str:
    exp = datetime.now() + timedelta(days=settings.refresh_ttl_days)
    return jwt.encode({"sub": user_id, "role": role, "type": "refresh", "exp": exp}, settings.jwt_secret, algorithm=ALGO)


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGO])
        if payload.get("type") != expected_type:
            raise ApiError(ErrorCode.TOKEN_INVALID, "Invalid token type", 401)
        return payload
    except JWTError as e:
        msg = str(e).lower()
        if "expired" in msg:
            raise ApiError(
                ErrorCode.TOKEN_EXPIRED if expected_type == "access" else ErrorCode.REFRESH_TOKEN_INVALID,
                "Token expired",
                401,
            )
        raise ApiError(
            ErrorCode.TOKEN_INVALID if expected_type == "access" else ErrorCode.REFRESH_TOKEN_INVALID,
            "Token invalid",
            401,
        )
