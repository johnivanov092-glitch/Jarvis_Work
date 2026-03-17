from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.jarvis_state import router as jarvis_state_router

app = FastAPI(title="Jarvis Work API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(jarvis_state_router)

@app.get("/health")
def health():
    return {"status": "ok"}
