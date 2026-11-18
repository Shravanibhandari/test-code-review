from fastapi import FastAPI
from app.api import router

app = FastAPI(title="Autonomous Code Review Agent")

app.include_router(router)


@app.get("/")
def home():
    return {
        "message": "Code Review Agent is Running Successfully!"
    }