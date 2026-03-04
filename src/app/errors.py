from dataclasses import dataclass
from typing import Any, Optional

from generated.models.error_code import ErrorCode

@dataclass
class ApiError(Exception):
    error_code: ErrorCode
    message: str
    status_code: int
    details: Optional[dict[str, Any]] = None
