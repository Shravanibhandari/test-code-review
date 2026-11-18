from fastapi import FastAPI

from app.api import router

app = FastAPI(title="Code Review & Refactoring Agent")
app.include_router(router)
