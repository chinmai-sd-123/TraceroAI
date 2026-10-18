from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.traces import router as traces_router
from app.api.routes.health import router as health_router
from app.api.routes.eval_runs import router as eval_runs_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.playground import router as playground_router
from app.api.routes.eval_grade import router as eval_grade_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.cost import start_price_refresh

configure_logging(
    json_logs=get_settings().app_env in ("staging", "production"),
    level=get_settings().log_level,
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    # Load live model prices off the request path; pricing uses the built-in
    # table until this lands.
    start_price_refresh()
    yield


app = FastAPI(
    title="TraceroAI API",
    version="0.1.0",
    description="Trace ingestion API for RAG observability and evaluation.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        *get_settings().cors_origins,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(traces_router)
app.include_router(eval_runs_router)
app.include_router(jobs_router)
app.include_router(playground_router)
app.include_router(eval_grade_router)