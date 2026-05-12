from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import products, telegram_bot
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables ready")
    except Exception as e:
        logger.warning(f"DB not ready at startup (will retry on first request): {e}")
    yield


app = FastAPI(title="Ruty Shop API", lifespan=lifespan)

cors_origins = os.getenv("CORS_ORIGINS")
if cors_origins:
    allow_origins = [
        origin.strip() for origin in cors_origins.split(",") if origin.strip()
    ]
else:
    allow_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
    if os.getenv("VERCEL"):
        allow_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(telegram_bot.router)


@app.get("/")
def health():
    return {"status": "ok"}
