from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine
from app.models import user as models
from app.api.v1.routes import auth, users

# Create Tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ez Bid Auth Backend")

# CORS
origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin]
if not origins:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router, prefix="/api", tags=["Auth"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])

@app.get("/")
def read_root():
    return {"status": "active", "message": "Service is running properly"}