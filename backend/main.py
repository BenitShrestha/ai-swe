from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.limiter import limiter
from backend.routes import router

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(router, prefix="/api")

# static frontend last, so /api/* isn't shadowed
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")