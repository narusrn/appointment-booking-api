import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import authentication, bookings

load_dotenv()  # populate os.environ from .env before any route reads it

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Appointment Booking API",
    description="Log in and book time slots. Admins see all bookings; other users see only their own.",
    version="1.0.0",
)
app.state.start_time = datetime.now()

app.include_router(authentication.router)
app.include_router(bookings.router)

app.add_middleware(
    CORSMiddleware,
    # ponytail: open for the test/demo; restrict to the real frontend origin(s) before prod
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Standard error shape for every failure mode: {"error": {"code": ..., "message": ...}}
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.status_code, "message": exc.detail}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": {"code": 422, "message": "Invalid request", "details": exc.errors()}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"code": 500, "message": "Internal server error"}},
    )


@app.get("/health", status_code=status.HTTP_200_OK, tags=["System"])
async def health_check():
    """Liveness probe."""
    return {
        "status": "online",
        "uptime": str(datetime.now() - app.state.start_time),
    }
