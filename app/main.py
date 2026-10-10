import logging
import os
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.models.schemas import HealthResponse, MetricsResponse
from app.routers.rag import limiter, router as rag_router
from app.services import metrics

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="RAG API - LangChain + Groq + Chroma",
    description="API production-ready untuk tanya-jawab dokumen PDF berbasis RAG (Retrieval Augmented Generation).",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_and_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    request.state.request_id = request_id

    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000

    response.headers["X-Request-ID"] = request_id
    metrics.record_latency_ms(duration_ms)
    if response.status_code >= 400:
        metrics.increment("errors")
    logger.info(
        "[%s] %s %s -> %d (%.1fms)",
        request_id, request.method, request.url.path, response.status_code, duration_ms,
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception("[%s] Unhandled exception on %s %s", request_id, request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Terjadi kesalahan internal pada server.", "request_id": request_id},
    )


app.include_router(rag_router)

# ---------- Halaman statis (landing, demo console, dashboard) ----------
_static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
_assets_dir = os.path.join(_static_dir, "assets")

if os.path.isdir(_assets_dir):
    app.mount("/static", StaticFiles(directory=_assets_dir), name="static-assets")


def _serve_page(filename: str):
    path = os.path.join(_static_dir, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"Halaman '{filename}' tidak ditemukan.")
    return FileResponse(path)


@app.get("/", include_in_schema=False)
async def landing_page():
    return _serve_page("landing.html")


@app.get("/demo", include_in_schema=False)
@app.get("/demo/", include_in_schema=False)
async def demo_page():
    return _serve_page("demo.html")


@app.get("/dashboard", include_in_schema=False)
@app.get("/dashboard/", include_in_schema=False)
async def dashboard_page():
    return _serve_page("dashboard.html")


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check():
    return HealthResponse(status="ok", env=settings.app_env)


@app.get("/api/v1/metrics", response_model=MetricsResponse, tags=["system"])
async def get_metrics():
    """Statistik pemakaian dasar. Sengaja dibuat publik (tidak butuh API key) supaya
    bisa ditampilkan di dashboard/landing page sebagai 'live stats'. Untuk production
    sungguhan dengan data sensitif, pertimbangkan proteksi tambahan atau agregasi lebih ketat."""
    return MetricsResponse(**metrics.snapshot())
