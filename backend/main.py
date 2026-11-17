"""
Fall Guard AI — Production REST API Backend.
Provides endpoints for Incident Management, Emergency Verification,
Caregiver Directory, and System Health.
"""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import db_manager
from backend.routers import auth, caregivers, care_management, incidents
from backend.security import ensure_bootstrap_users, get_current_user

app = FastAPI(
    title="Fall Guard AI — Real-Time Human Fall Detection API",
    description="Context-Aware Computer Vision, Emergency Verification State Machine, and Caregiver Alert Services.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for local dashboards and external nodes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(care_management.router)
app.include_router(incidents.router, dependencies=[Depends(get_current_user)])
app.include_router(caregivers.router, dependencies=[Depends(get_current_user)])


@app.on_event("startup")
def seed_authentication_accounts():
    ensure_bootstrap_users()


@app.get("/")
def root():
    return {
        "system": "Fall Guard AI Backend",
        "version": "2.0.0",
        "status": "ONLINE",
        "documentation": "/docs",
        "database": "MongoDB (Active)" if db_manager.is_connected else "Local Persistent Storage Engine",
    }


@app.get("/api/health")
def api_health():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "system": "Fall Guard AI",
        "mongodb_connected": db_manager.is_connected,
        "database_mode": "MongoDB" if db_manager.is_connected else "Local JSON Storage",
    }


@app.get("/api/status")
def api_status():
    """System monitoring and active incident status endpoint."""
    recent_incidents = db_manager.find("incidents", limit=5)
    pending_count = len([i for i in recent_incidents if i.get("verification_status") == "PENDING_VERIFICATION"])

    return {
        "status": "MONITORING_ACTIVE",
        "pending_verifications": pending_count,
        "total_recent_incidents": len(recent_incidents),
        "database_connected": db_manager.is_connected,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
