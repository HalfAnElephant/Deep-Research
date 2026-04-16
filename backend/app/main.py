from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.database import init_db

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


frontend_dist_dir = Path(settings.frontend_dist_dir)
if frontend_dist_dir.exists():
    resolved_frontend_dist_dir = frontend_dist_dir.resolve()
    assets_dir = frontend_dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    def serve_frontend_index() -> FileResponse:
        return FileResponse(frontend_dist_dir / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend_app(full_path: str) -> FileResponse:
        if full_path.startswith(("api/", "docs", "redoc", "openapi.json", "healthz")):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (frontend_dist_dir / full_path).resolve()
        try:
            candidate.relative_to(resolved_frontend_dist_dir)
        except ValueError:
            return FileResponse(frontend_dist_dir / "index.html")
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(frontend_dist_dir / "index.html")
