"""
vector_store.py — semua urusan dengan database vektor (ChromaDB).

Istilah penting:
  - Vector store  : database yang menyimpan teks beserta vektor (angka) maknanya.
  - Collection    : "folder/namespace" di dalam database. Satu collection bisa berisi banyak PDF.
  - Chunk         : potongan kecil dokumen; satu baris di database = satu chunk.

Alur pencarian: pertanyaan -> diubah jadi vektor -> dicari chunk dengan vektor TERDEKAT.
"""
import logging
import os
import re

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.core.config import get_settings
from app.services.model_provider import get_embeddings

logger = logging.getLogger(__name__)

# Regex: cocokkan semua karakter yang BUKAN huruf/angka/_/- (tanda ^ berarti "selain").
_COLLECTION_NAME_RE = re.compile(r"[^a-zA-Z0-9_-]")
_SLUG_RE = re.compile(r"[^a-zA-Z0-9._-]")


def sanitize_collection_name(name: str) -> str:
    """Chroma hanya menerima nama collection huruf/angka/_/-, panjang 3-63 karakter.
    Fungsi ini membersihkan nama dari user supaya selalu valid."""
    cleaned = _COLLECTION_NAME_RE.sub("_", name).strip("_-")
    if len(cleaned) < 3:
        cleaned = f"col_{cleaned}"
    return cleaned[:63]


def _persist_dir() -> str:
    """
    Folder penyimpanan database, DIPISAH per model embedding.

    Kenapa? Vektor dari model A dan model B tidak bisa dibandingkan (ruang maknanya beda).
    Kalau Anda mengganti EMBEDDING_MODEL tapi database lama tetap dipakai, hasil pencarian
    jadi ngawur (dan ini salah satu penyebab jawaban "tidak sesuai PDF").
    Dengan folder terpisah per model, ganti model = otomatis database baru yang bersih.
    """
    settings = get_settings()
    slug = _SLUG_RE.sub("_", settings.embedding_model)
    path = os.path.join(settings.chroma_dir, slug)
    os.makedirs(path, exist_ok=True)
    return path


def get_vector_store(collection_name: str) -> Chroma:
    """Buka (atau buat kalau belum ada) satu collection."""
    return Chroma(
        collection_name=sanitize_collection_name(collection_name),
        embedding_function=get_embeddings(),
        persist_directory=_persist_dir(),
        # "cosine" = ukuran jarak berbasis sudut antar vektor; cocok untuk teks.
        # Jarak 0 = identik, makin besar = makin berbeda.
        collection_metadata={"hnsw:space": "cosine"},
    )


def _build_where(source_filter: list[str] | None) -> dict | None:
    """Susun filter metadata Chroma: batasi pencarian ke file tertentu saja (opsional)."""
    if not source_filter:
        return None
    if len(source_filter) == 1:
        return {"source": source_filter[0]}
    return {"source": {"$in": source_filter}}  # $in = "salah satu dari daftar ini"


def retrieve_documents(
    collection_name: str,
    query: str,
    k: int,
    source_filter: list[str] | None = None,
) -> list[Document]:
    """
    Cari k chunk yang paling mirip maknanya dengan `query`.

    Kenapa tidak pakai store.as_retriever() bawaan LangChain?
    Karena kalau di database ada baris yang kolom teksnya kosong (None) — misalnya sisa
    data rusak — LangChain langsung crash dengan error
    "Input should be a valid string [page_content]". Dengan memanggil Chroma langsung,
    baris rusak seperti itu bisa kita LEWATI dan pencarian tetap berjalan.
    """
    store = get_vector_store(collection_name)

    # 1) Ubah pertanyaan jadi vektor memakai model embedding yang sama dengan saat upload.
    query_vector = get_embeddings().embed_query(query)

    # 2) Minta lebih banyak dari k (k*2) sebagai cadangan, karena sebagian mungkin kita buang.
    result = store._collection.query(
        query_embeddings=[query_vector],
        n_results=max(k * 4, k + 4),
        where=_build_where(source_filter),
        include=["documents", "metadatas", "distances"],
    )

    # Hasil Chroma berbentuk list-di-dalam-list (satu list per query; kita hanya kirim 1 query).
    texts = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    docs: list[Document] = []
    skipped = 0
    seen: set[tuple] = set()  # (file, halaman, teks) yang sudah diambil -> buang salinan kembar
    for text, meta, dist in zip(texts, metadatas, distances):
        if not text or not text.strip():
            skipped += 1  # baris rusak/kosong -> lewati
            continue
        key = ((meta or {}).get("source"), (meta or {}).get("page"), text)
        if key in seen:
            continue  # data lama yang terupload berkali-kali
        seen.add(key)
        metadata = dict(meta or {})
        # Untuk jarak cosine, kemiripan = 1 - jarak. Kita simpan agar bisa ditampilkan ke user.
        metadata["score"] = round(max(0.0, 1.0 - float(dist)), 3)
        docs.append(Document(page_content=text, metadata=metadata))
        if len(docs) >= k:
            break

    if skipped:
        logger.warning(
            "Collection '%s': %d baris kosong dilewati saat pencarian (data lama yang rusak?)",
            collection_name, skipped,
        )
    return docs


def list_documents_in_collection(collection_name: str) -> list[str]:
    """Daftar nama file unik yang sudah diindex dalam satu collection."""
    store = get_vector_store(collection_name)
    raw = store.get(include=["metadatas"])
    # {…for…} = "set comprehension": mengumpulkan nilai unik (set tidak menyimpan duplikat).
    sources = {m.get("source") for m in raw.get("metadatas", []) if m and m.get("source")}
    return sorted(sources)


def list_collections() -> list[str]:
    """Daftar semua collection. Memakai client Chroma langsung supaya tidak ikut
    membuat collection tambahan bernama 'langchain' (bug versi sebelumnya)."""
    client = chromadb.PersistentClient(path=_persist_dir())
    # Chroma 0.5 mengembalikan objek Collection, versi lebih baru mengembalikan string nama.
    return sorted(c if isinstance(c, str) else c.name for c in client.list_collections())


def delete_document_from_collection(collection_name: str, source_filename: str) -> int:
    """Hapus semua chunk milik SATU file (dokumen lain di collection yang sama tetap aman).
    Mengembalikan jumlah chunk yang dihapus."""
    store = get_vector_store(collection_name)
    raw = store.get(where={"source": source_filename}, include=["metadatas"])
    ids_to_delete = raw.get("ids", [])
    if not ids_to_delete:
        return 0
    store.delete(ids=ids_to_delete)
    logger.info("Menghapus %d chunk '%s' dari collection '%s'",
                len(ids_to_delete), source_filename, collection_name)
    return len(ids_to_delete)


def delete_collection(collection_name: str) -> None:
    """Hapus satu collection beserta seluruh isinya."""
    get_vector_store(collection_name).delete_collection()
    logger.info("Collection dihapus: %s", sanitize_collection_name(collection_name))