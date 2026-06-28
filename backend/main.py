from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uvicorn

app = FastAPI(title="TaxEase Filing API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Route registration (must come after app is defined)
import backend.app.v1.login_signup  # noqa: F401, E402


@app.on_event("startup")
async def on_startup():
    from backend.db.database import create_tables
    await create_tables()


@app.get("/")
async def root(request: Request):
    return {
        "message": "Welcome to TaxEase Filing API",
        "path": request.url.path,
        "time": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)