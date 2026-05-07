from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from service.db import Base, engine

logger = logging.getLogger(__name__)
def configure_logging() -> None:
    os.makedirs("logs", exist_ok=True)

    file_handler = TimedRotatingFileHandler(
        filename="logs/app.log",
        when="midnight",
        interval=1,
        backupCount=14,
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d"

    formatter = logging.Formatter(
        "[%(asctime)s][%(levelname)s][%(name)s]: %(message)s"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


configure_logging()
logger.info("Logging configured.")

from service.app_services import analysis_service, mongo_db_service, reddit_api_service, twitter_api_service
from api.routes.twitter import router as twitter_router
from api.routes.reddit import router as reddit_router
from api.routes.auth import router as auth_router
from api.routes.analysis import router as analysis_router

Base.metadata.create_all(bind=engine)
logger.info("[Database] Tables created successfully.")

app = FastAPI(
    title="Refract API",
    version="1.0.0",
)

origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8081"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    twitter_router,
    prefix="/api",
    tags=["twitter"],
)

app.include_router(
    reddit_router,
    prefix="/api",
    tags=["reddit"],
)

app.include_router(
    auth_router,
    prefix="/api",
    tags=["app auth"],
)

app.include_router(
    analysis_router,
    prefix="/api",
    tags=["analysis"],
)
# Routes
@app.get("/")
async def root():
    logger.info("Root endpoint accessed.")
    return {"message": "Refract API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}



def run():
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, env_file='.env')
    logger.info("API server started successfully.")
