from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    filename: str
    collection: str
    num_chunks: int
    num_pages: int
    message: str = "Dokumen berhasil diproses dan diindex."


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    collection: str = Field(..., min_length=1, max_length=100)
    source_filter: list[str] | None = Field(
        default=None,
        description="Opsional. Batasi pencarian hanya ke file tertentu dalam collection ini "
                    "(nama file persis seperti saat diupload, misal 'laporan-2025.pdf'). "
                    "Kosongkan untuk mencari di seluruh dokumen dalam collection.",
    )


class SourceItem(BaseModel):
    source: str
    page: int | None = None
    snippet: str
    # Skor kemiripan 0-1 antara pertanyaan dan potongan dokumen (makin tinggi makin relevan).
    score: float | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceItem]


class ChatRequest(BaseModel):
    session_id: str = Field(
        ..., min_length=1, max_length=100,
        description="ID unik percakapan (buat sendiri di client, misal UUID). "
                    "Dipakai untuk menjaga konteks pertanyaan lanjutan (multi-turn).",
    )
    question: str = Field(..., min_length=1, max_length=2000)
    collection: str = Field(..., min_length=1, max_length=100)
    source_filter: list[str] | None = None


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: list[SourceItem]
    standalone_question: str = Field(
        description="Pertanyaan yang sudah 'dipadatkan' dari riwayat percakapan, dipakai untuk retrieval."
    )


class CollectionsResponse(BaseModel):
    collections: list[str]


class DocumentsInCollectionResponse(BaseModel):
    collection: str
    documents: list[str]


class ErrorResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: str
    env: str


class MetricsResponse(BaseModel):
    uptime_seconds: float
    total_uploads: int
    total_queries: int
    total_chats: int
    total_errors: int
    total_requests_tracked: int
    avg_response_time_ms: float
