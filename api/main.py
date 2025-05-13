from fastapi import FastAPI
from routers import transcripciones

app = FastAPI()
app.include_router(transcripciones.router, prefix="/transcripciones")
