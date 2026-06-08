from contextlib import asynccontextmanager
from pathlib import Path

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import client, ping_database

settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

if settings.summary_debug or settings.debug_summary:
    logging.getLogger("app.services.summary_reference_summarizer").setLevel(logging.INFO)
    logging.getLogger("app.services.summary_service").setLevel(logging.INFO)
    logging.getLogger("app.api.routes.summary").setLevel(logging.INFO)

if settings.rag_debug:
    logging.getLogger("app.services.rag_service").setLevel(logging.INFO)
    logging.getLogger("app.services.chat_service").setLevel(logging.INFO)
    logging.getLogger("app.api.routes.chat").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    try:
        await ping_database()
        app.state.database_status = "ok"
    except Exception as error:
        app.state.database_status = f"error: {error}"
    yield
    client.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):3000",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
def database_healthcheck() -> dict[str, str]:
    return {"database": getattr(app.state, "database_status", "unknown")}
