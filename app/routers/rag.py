import json
import logging
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.security import verify_api_key
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    CollectionsResponse,
    DocumentsInCollectionResponse,
    QueryRequest,
    QueryResponse,
    UploadResponse,
)
from app.services import metrics
from app.services.chat_history import append_turn, clear_session, get_history_messages
from app.services.ingestion import IngestionError, ingest_pdf, save_upload_file
from app.services.rag_chain import (
    RetrievalEmptyError,
    prepare_conversational_stream,
    query_rag,
    query_rag_conversational,
)
from app.services.vector_store import (
    delete_collection,
    delete_document_from_collection,
    list_collections,
    list_documents_in_collection,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["rag"], dependencies=[Depends(verify_api_key)])
limiter = Limiter(key_func=get_remote_address)


def _friendly_error(e: Exception) -> tuple[int, str]:
    """Terjemahkan error teknis menjadi (status HTTP, pesan) yang bisa dipahami pengguna.
    Pesan ini muncul sebagai notifikasi merah di halaman demo."""
    text = str(e).lower()
    if "rate_limit" in text or "429" in text or "rate limit" in text:
        return 429, "Batas pemakaian gratis Groq tercapai. Tunggu sekitar 1 menit lalu coba lagi."
    if "model_not_found" in text or "does not exist" in text:
        return 502, ("Model LLM tidak tersedia di Groq (mungkin sudah dihentikan). "
                     "Ganti LLM_MODEL di file .env, misalnya openai/gpt-oss-120b, lalu restart server.")
    if "model_not_found" in text or "does not exist" in text:
        return 502, ("Model LLM tidak tersedia untuk akun Groq Anda. Ganti LLM_MODEL di file .env "
                     "dengan model yang ada di akun Anda, lalu restart server.")
    if "api key" in text or "invalid_api_key" in text or "401" in text:
        return 502, "GROQ_API_KEY tidak valid. Periksa kembali isi file .env Anda."
    if "connection" in text or "timeout" in text or "timed out" in text:
        return 503, "Tidak bisa terhubung ke layanan AI. Periksa koneksi internet server."
    return 500, f"Terjadi kesalahan saat memproses permintaan: {e}"


@router.post("/upload", response_model=UploadResponse)
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    # PENTING: `Form(...)` membuat FastAPI membaca `collection` dari BODY form (multipart), yaitu
    # tempat curl `-F "collection=..."` dan JavaScript `FormData.append(...)` mengirimnya.
    # Tanpa `Form`, parameter biasa dianggap QUERY STRING (`/upload?collection=...`) sehingga
    # nilai dari form DIABAIKAN dan semua dokumen diam-diam masuk ke "default".
    collection: str = Form("default"),
):
    settings = get_settings()

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Hanya file PDF yang didukung.")

    file_bytes = await file.read()
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            status_code=413,
            detail=f"File terlalu besar ({size_mb:.1f}MB). Maksimal {settings.max_upload_size_mb}MB.",
        )
    if size_mb == 0:
        raise HTTPException(status_code=400, detail="File kosong.")

    saved_path = save_upload_file(file_bytes, file.filename)

    try:
        result = ingest_pdf(saved_path, collection_name=collection, source_filename=file.filename)
    except IngestionError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    finally:
        # Bersihkan file sementara setelah diproses
        if os.path.exists(saved_path):
            os.remove(saved_path)

    metrics.increment("uploads")
    return UploadResponse(**result)


@router.post("/query", response_model=QueryResponse)
@limiter.limit("30/minute")
async def query_document(request: Request, body: QueryRequest):
    try:
        result = query_rag(
            body.question,
            collection_name=body.collection,
            source_filter=body.source_filter,
        )
    except RetrievalEmptyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception("Query RAG gagal")
        status, message = _friendly_error(e)
        raise HTTPException(status_code=status, detail=message) from e

    metrics.increment("queries")
    return QueryResponse(**result)


@router.get("/collections", response_model=CollectionsResponse)
async def get_collections():
    return CollectionsResponse(collections=list_collections())


@router.get("/collections/{collection_name}/documents", response_model=DocumentsInCollectionResponse)
async def get_documents_in_collection(collection_name: str):
    documents = list_documents_in_collection(collection_name)
    return DocumentsInCollectionResponse(collection=collection_name, documents=documents)


@router.delete("/collections/{collection_name}/documents/{filename}")
async def remove_document(collection_name: str, filename: str):
    deleted_count = delete_document_from_collection(collection_name, filename)
    if deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail=f"File '{filename}' tidak ditemukan di collection '{collection_name}'.",
        )
    return {
        "message": f"File '{filename}' berhasil dihapus dari collection '{collection_name}'.",
        "chunks_deleted": deleted_count,
    }


@router.delete("/collections/{collection_name}")
async def remove_collection(collection_name: str):
    try:
        delete_collection(collection_name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Collection tidak ditemukan atau gagal dihapus: {e}") from e
    return {"message": f"Collection '{collection_name}' berhasil dihapus."}


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat(request: Request, body: ChatRequest):
    """RAG multi-turn: mengingat riwayat percakapan per session_id, sehingga pertanyaan
    lanjutan seperti 'kalau dibanding tahun lalu?' bisa dipahami tanpa perlu diulang detailnya."""
    history = get_history_messages(body.session_id)

    try:
        result = query_rag_conversational(
            body.question,
            collection_name=body.collection,
            history=history,
            source_filter=body.source_filter,
        )
    except RetrievalEmptyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception("Chat RAG gagal")
        status, message = _friendly_error(e)
        raise HTTPException(status_code=status, detail=message) from e

    append_turn(body.session_id, body.question, result["answer"])
    metrics.increment("chats")
    return ChatResponse(session_id=body.session_id, **result)


@router.post("/chat/stream")
@limiter.limit("20/minute")
async def chat_stream(request: Request, body: ChatRequest):
    """Sama seperti /chat, tapi jawaban di-stream token-by-token (Server-Sent Events)
    supaya bisa ditampilkan secara real-time di frontend, seperti ChatGPT."""
    history = get_history_messages(body.session_id)

    try:
        token_gen, sources, standalone_question = prepare_conversational_stream(
            body.question,
            collection_name=body.collection,
            history=history,
            source_filter=body.source_filter,
        )
    except RetrievalEmptyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception("Chat stream RAG gagal")
        status, message = _friendly_error(e)
        raise HTTPException(status_code=status, detail=message) from e

    async def event_stream():
        full_answer = ""
        try:
            async for token in token_gen:
                full_answer += token
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("Streaming gagal di tengah jalan")
            yield f"data: {json.dumps({'error': _friendly_error(e)[1]}, ensure_ascii=False)}\n\n"
            return

        append_turn(body.session_id, body.question, full_answer)
        metrics.increment("chats")
        final_payload = {
            "done": True,
            "sources": sources,
            "standalone_question": standalone_question,
        }
        yield f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.delete("/chat/{session_id}")
async def clear_chat_history(session_id: str):
    clear_session(session_id)
    return {"message": f"Riwayat percakapan session '{session_id}' berhasil dihapus."}