from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from generated.models.error_code import ErrorCode
from .auth import decode_token
from .errors import ApiError

bearer = HTTPBearer(auto_error=False)

class Principal:
    def __init__(self, user_id: str, role: str):
        self.user_id = user_id
        self.role = role


async def get_principal(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Principal:
    if creds is None:
        raise ApiError(ErrorCode.TOKEN_INVALID, "Missing bearer token", 401)
    payload = decode_token(creds.credentials, expected_type="access")
    principal = Principal(user_id=payload["sub"], role=payload["role"])
    request.state.user_id = principal.user_id
    request.state.role = principal.role
    return principal


def require_roles(*allowed: str):
    async def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in allowed:
            raise ApiError(ErrorCode.ACCESS_DENIED, "Access denied", 403)
        return principal
    return _dep
