"""
model_provider.py — tempat membuat 2 "model AI" yang dipakai aplikasi:

  1. Embeddings : mengubah teks -> vektor angka (untuk MENCARI potongan dokumen relevan)
  2. LLM        : model bahasa yang MENULIS jawaban berdasarkan potongan yang ditemukan

Keduanya dibuat sekali lalu dipakai ulang (lru_cache), karena memuat model itu mahal
(embedding butuh beberapa detik + RAM; membuat ulang tiap request akan sangat lambat).
"""
import logging
from functools import lru_cache

from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class PrefixedEmbeddings(HuggingFaceEmbeddings):
    """
    Pembungkus embedding yang menambahkan awalan teks sebelum diubah jadi vektor.

    Kenapa perlu? Model keluarga E5 (seperti multilingual-e5-small) dilatih dengan aturan:
      - teks DOKUMEN diawali  "passage: "
      - teks PERTANYAAN diawali "query: "
    Kalau awalan ini dilupakan, kualitas pencarian turun cukup jauh. Model lain (misal MiniLM)
    tidak butuh awalan, jadi untuk model itu kedua awalan dibiarkan kosong.

    Ini contoh "inheritance" (pewarisan): kita ambil semua fitur HuggingFaceEmbeddings,
    lalu hanya mengubah dua method: embed_query dan embed_documents.
    """

    query_prefix: str = ""
    doc_prefix: str = ""

    def embed_query(self, text: str) -> list[float]:
        # Dipanggil saat user BERTANYA -> ubah pertanyaan jadi vektor.
        return super().embed_query(self.query_prefix + text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # Dipanggil saat UPLOAD -> ubah banyak chunk dokumen jadi vektor sekaligus.
        return super().embed_documents([self.doc_prefix + t for t in texts])


@lru_cache
def get_embeddings() -> PrefixedEmbeddings:
    settings = get_settings()
    name = settings.embedding_model
    logger.info("Memuat model embedding: %s", name)

    # Peringatan dini kalau masih memakai model khusus bahasa Inggris (kasus .env lama).
    if name.endswith("all-MiniLM-L6-v2"):
        logger.warning(
            "Model embedding '%s' hanya untuk bahasa Inggris — hasil pencarian dokumen "
            "Indonesia akan kurang akurat. Ganti EMBEDDING_MODEL ke 'intfloat/multilingual-e5-small'.",
            name,
        )

    is_e5 = "e5" in name.lower()
    return PrefixedEmbeddings(
        model_name=name,
        model_kwargs={"device": "cpu"},  # jalan di CPU, tidak butuh GPU
        # normalize_embeddings=True membuat panjang vektor = 1, sehingga ukuran kemiripan
        # (cosine) stabil dan mudah dibandingkan.
        encode_kwargs={"normalize_embeddings": True},
        query_prefix="query: " if is_e5 else "",
        doc_prefix="passage: " if is_e5 else "",
    )


@lru_cache
def get_llm() -> ChatGroq:
    settings = get_settings()
    logger.info("Menyiapkan LLM Groq: %s", settings.llm_model)
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.llm_model,
        # temperature = tingkat "kreativitas". 0 = konsisten/faktual, 1 = bebas/kreatif.
        # Untuk tanya-jawab dokumen kita ingin jawaban setia pada fakta -> nilai rendah.
        temperature=0.1,
        max_retries=2,  # kalau gagal sementara (jaringan), coba ulang maksimal 2x
        timeout=60,     # batas tunggu 60 detik
    )
