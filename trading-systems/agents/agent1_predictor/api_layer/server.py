"""
api_layer/server.py
===================
FastAPI Entry Point for the Agent 1 Predictor Service.
To run: 
    uvicorn api_layer.server:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import sys

# Ensure root directory is on the path so internal imports work seamlessly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api_layer.analysis_routes import router as analysis_router
from logger import get_logger

logger = get_logger()

# Initialize FastAPI App
app = FastAPI(
    title="Agent 1 Predictor API",
    description="Real-time multi-indicator AI financial analysis engine.",
    version="2.0.0"
)

# Allow CORS for future React dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(analysis_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "status": "online",
        "agent": "Agent 1 Predictor",
        "docs_url": "/docs"
    }

@app.on_event("startup")
async def startup_event():
    logger.info("FastAPI Server Started: Agent 1 Predictor is online.")
