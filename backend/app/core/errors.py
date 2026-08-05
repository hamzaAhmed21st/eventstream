from __future__ import annotations

import math
from collections.abc import Mapping

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

type JsonSafeScalar = bool | int | float | str | None
type JsonSafeValue = JsonSafeScalar | list[JsonSafeValue] | dict[str, JsonSafeValue]


async def validation_exception_handler(
    request: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    del request
    content = jsonable_encoder({"detail": _make_json_safe(exception.errors())})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=content,
    )


def _make_json_safe(value: object) -> JsonSafeValue:
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if value == math.inf:
            return "Infinity"
        if value == -math.inf:
            return "-Infinity"
        return value
    if isinstance(value, Mapping):
        return {str(key): _make_json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_make_json_safe(item) for item in value]
    return str(value)
