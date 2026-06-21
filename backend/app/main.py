from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.experiments import router as experiments_router
from app.api.projects import router as projects_router
from app.api.prompts import router as prompts_router
from app.api.reports import router as reports_router
from app.api.tests import router as tests_router
from app.api.versions import router as versions_router
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import setup_logging
from app.models.base import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(versions_router)
app.include_router(prompts_router)
app.include_router(tests_router)
app.include_router(experiments_router)
app.include_router(reports_router)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "data": None, "error": exc.message},
    )


@app.get("/api/v1/health")
async def health_check():
    return {"success": True, "data": {"status": "healthy"}, "error": None}
