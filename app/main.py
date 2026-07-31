"""Create the FastAPI application and mount analytics routes."""

from fastapi import FastAPI

from app.api.analytics import router as analytics_router

app = FastAPI(title="Tech Job Market Pipeline API")

app.include_router(analytics_router, prefix="/analytics")
