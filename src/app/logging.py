import time, uuid
from datetime import datetime, timezone
from fastapi import Request
import orjson


def check(obj):
    if isinstance(obj, dict):
        return {k: ("***" if k.lower() == "password" else check(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [check(x) for x in obj]
    return obj


async def logging(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start = time.perf_counter()

    body = None
    if request.method in ("POST","PUT","DELETE"):
        try:
            raw = await request.body()
            if raw:
                body = check(orjson.loads(raw))
        except Exception:
            body = {"error": "cant parse"}

    response= await call_next(request)
    response.headers["X-Request-Id"] = request_id
    duration_ms = int((time.perf_counter() - start) * 1000)

    log_record = {
        "request_id": request_id,
        "method": request.method,
        "endpoint": request.url.path,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
        "user_id": getattr(request.state, "user_id", None),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if body is not None:
        log_record["request_body"] = body

    print(orjson.dumps(log_record).decode("utf-8"))
    return response
