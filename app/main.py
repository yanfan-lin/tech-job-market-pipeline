from fastapi import FastAPI

# Import analytics router
from app.api.analytics import router as analytics_router

# Create app
app = FastAPI(title="Tech Job Market Pipeline API")


# Add routes under /analytics
app.include_router(analytics_router, prefix="/analytics")