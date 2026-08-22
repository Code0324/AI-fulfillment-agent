"""
Amazon AI Fulfillment Assistant - FastAPI Backend

Chunk 1A: Project Foundation
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Amazon AI Fulfillment Assistant",
    description="AI-powered order fulfillment workspace for Amazon sellers",
    version="0.1.0",
)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
