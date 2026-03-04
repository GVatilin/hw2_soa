from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from generated.models.error_code import ErrorCode
from .logging import logging
from .errors import ApiError
from .api import router as api_router


app = FastAPI(default_response_class=ORJSONResponse)
app.middleware("http")(logging)
app.include_router(api_router)


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, e: ApiError):
    return ORJSONResponse(
        status_code=e.status_code,
        content={"error_code": e.error_code.value, "message": e.message, "details": e.details},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, e: RequestValidationError):
    serialized_errors = jsonable_encoder(
        e.errors(),
        custom_encoder={ValueError: lambda v: str(v)},
    )
    return ORJSONResponse(
        status_code=400,
        content={
            "error_code": ErrorCode.VALIDATION_ERROR.value,
            "message": "Validation error",
            "details": {"errors": serialized_errors},
        },
    )
