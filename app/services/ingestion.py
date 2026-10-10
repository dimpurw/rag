"""
ingestion.py — proses memasukkan PDF ke database ("ingest").

Alur:  PDF -> baca teks per halaman -> potong jadi chunk -> hitung vektor -> simpan ke Chroma
"""
import logging
import os
import uuid

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)


class IngestionError(Exception):
    """Error khusus untuk kegagalan proses upload; pesannya ditampilkan ke user."""


def ingest_pdf(file_path: str, collection_name: str, source_filename: str) -> dict:
    settings = get_settings()

    # --- 1. Baca PDF. PyPDFLoader menghasilkan 1 "Document" per halaman. ---
    try:
        documents = PyPDFLoader(file_path).load()
    except Exception as e:
        logger.exception("Gagal membaca PDF: %s", file_path)
        raise IngestionError(f"Gagal membaca file PDF: {e}") from e

    if not documents:
        raise IngestionError("PDF tidak berisi halaman yang bisa dibaca.")

    # --- 2. Potong jadi chunk. ---
    # RecursiveCharacterTextSplitter mencoba memotong di batas "alami" dulu
    # (paragraf, lalu baris, lalu kalimat, lalu kata) supaya potongan tetap enak dibaca.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    chunks = splitter.split_documents(documents)

    # --- 3. Buang chunk kosong. ---
    # PDF hasil scan/gambar tidak punya teks; chunk kosong yang tersimpan di database
    # akan membuat error saat pencarian. Lebih aman dibuang sejak awal.
    chunks = [c for c in chunks if c.page_content and c.page_content.strip()]
    if not chunks:
        raise IngestionError(
            "Tidak ada teks yang bisa dibaca dari PDF ini (kemungkinan hasil scan/gambar). "
            "Gunakan PDF yang teksnya bisa diseleksi/di-copy."
        )

    # --- 4. Lengkapi metadata tiap chunk. ---
    # Metadata = "label" yang ikut tersimpan: dari file mana, halaman berapa, id uniknya.
    ids = []
    for chunk in chunks:
        chunk.metadata["source"] = source_filename
        # PyPDF menghitung halaman dari 0, sedangkan pembaca PDF dari 1.
        # Tanpa +1, sitasi "halaman 1" sebenarnya halaman 2 di PDF (salah satu sumber
        # keluhan "tidak sesuai dengan PDF").
        chunk.metadata["page"] = int(chunk.metadata.get("page", 0)) + 1
        chunk_id = str(uuid.uuid4())  # uuid4 = ID acak yang hampir pasti unik
        chunk.metadata["chunk_id"] = chunk_id
        ids.append(chunk_id)

    # --- 5. Hitung vektor & simpan. add_documents memanggil model embedding otomatis. ---
    store = get_vector_store(collection_name)

    # Upload ulang file bernama sama = GANTI, bukan tambah. Tanpa ini, tiap upload menambah salinan
    # yang sama persis; saat pencarian, 6 hasil teratas bisa berisi salinan kembar dari 1-2 potongan
    # saja sehingga potongan lain (dan jawabannya) tidak ikut terkirim ke LLM.
    old = store.get(where={"source": source_filename}, include=[])
    if old.get("ids"):
        store.delete(ids=old["ids"])
        logger.info("Mengganti '%s': %d chunk lama dihapus", source_filename, len(old["ids"]))

    try:
        store.add_documents(documents=chunks, ids=ids)
    except Exception as e:
        logger.exception("Gagal menyimpan ke Chroma")
        raise IngestionError(f"Gagal menyimpan ke vector store: {e}") from e

    logger.info("Ingest '%s' -> collection '%s': %d chunk", source_filename, collection_name, len(chunks))
    return {
        "filename": source_filename,
        "collection": collection_name,
        "num_chunks": len(chunks),
        "num_pages": len(documents),
    }


def save_upload_file(file_bytes: bytes, filename: str) -> str:
    """Simpan file upload sementara ke disk agar bisa dibaca PyPDFLoader (butuh path file)."""
    settings = get_settings()
    os.makedirs(settings.upload_dir, exist_ok=True)
    # os.path.basename mencegah serangan "path traversal" (nama file seperti ../../etc/passwd).
    safe_name = f"{uuid.uuid4().hex}_{os.path.basename(filename)}"
    dest_path = os.path.join(settings.upload_dir, safe_name)
    with open(dest_path, "wb") as f:
        f.write(file_bytes)
    return dest_path