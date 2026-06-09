from fastapi import FastAPI
from app.api.routes.traces import router as traces_router
from app.api.routes.health import router as health_router

app = FastAPI(
    title="TraceroAI API",
    version="0.1.0",
    description="Trace ingestion API for RAG observability and evaluation.",
)

app.include_router(health_router)
app.include_router(traces_router)