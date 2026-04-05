# Start the FastAPI app and register analytics routes

from fastapi import FastAPI

# Import analytics router
from app.api.analytics import router as analytics_router

# Create the FastAPI app
app = FastAPI(title="Tech Job Market Pipeline API")


# Register analytics routes under /analytics
app.include_router(analytics_router, prefix="/analytics")