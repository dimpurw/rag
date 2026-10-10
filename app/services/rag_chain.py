"""
rag_chain.py — INTI dari RAG (Retrieval-Augmented Generation).

RAG = "cari dulu, baru jawab":
  1. RETRIEVAL  : cari potongan dokumen yang relevan dengan pertanyaan
  2. AUGMENTED  : tempelkan potongan itu ke dalam prompt sebagai "konteks"
  3. GENERATION : minta LLM menjawab HANYA berdasarkan konteks tersebut

Dengan begitu LLM menjawab dari dokumen Anda, bukan dari ingatan/karangannya sendiri.
"""
import logging

from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import StrOutputParser
# ChatPromptTemplate = "cetakan" prompt dengan lubang {variabel} yang diisi saat dijalankan.
# MessagesPlaceholder = lubang khusus untuk menyisipkan RIWAYAT percakapan.
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.core.config import get_settings
from app.services.model_provider import get_llm
from app.services.vector_store import retrieve_documents

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# PROMPT: instruksi yang diberikan ke LLM. Kualitas jawaban sangat bergantung di sini.
# ----------------------------------------------------------------------------
SYSTEM_PROMPT = """Kamu adalah asisten yang menjawab pertanyaan HANYA berdasarkan konteks dokumen di bawah.

Aturan wajib:
1. Jawab dalam bahasa yang sama dengan pertanyaan pengguna.
2. Gunakan HANYA informasi dari konteks. Jangan menambah fakta dari pengetahuanmu sendiri.
3. Kutip angka, nama, dan tanggal PERSIS seperti tertulis di konteks. Jangan membulatkan atau menghitung ulang kecuali diminta.
4. Pada data tabel, perhatikan urutan kolom pada baris header (misalnya "2025 2024") sebelum membaca angkanya.
5. Baca SEMUA sumber di konteks sebelum menyimpulkan. Hanya jika jawabannya benar-benar tidak ada di salah satu sumber, jawab: "Informasi tersebut tidak ditemukan di dokumen yang diupload." Jangan menebak.
6. Untuk pertanyaan spesifik, jawab ringkas dan langsung ke inti. Untuk permintaan umum ("isi dokumen", "ringkasan", "jelaskan semuanya", "apa saja"), uraikan SEMUA bagian/pasal/poin yang ada di konteks secara berurutan, jangan hanya memilih sebagian.
7. Sebutkan sumbernya dengan format (nama file, hal. N).

Konteks dokumen:
{context}
"""

# Prompt untuk tanya-jawab sekali putus: [aturan sistem] + [pertanyaan].
_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{question}"),
])

# Prompt untuk chat multi-turn: ditambah riwayat percakapan di tengahnya.
_chat_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder("history"),
    ("human", "{question}"),
])

# Prompt "condense": mengubah pertanyaan lanjutan menjadi pertanyaan yang berdiri sendiri.
# Contoh: riwayat "Berapa laba 2025?" lalu user tanya "kalau 2024?"
#         -> diubah jadi "Berapa laba 2024?" supaya pencarian dokumen tahu apa yang dicari.
_CONDENSE_SYSTEM = (
    "Ubah pertanyaan lanjutan berikut menjadi SATU pertanyaan mandiri yang bisa dipahami tanpa "
    "riwayat percakapan, dalam bahasa yang sama. Pertahankan semua istilah, angka, dan nama penting. "
    "Jika pertanyaan sudah mandiri, kembalikan apa adanya. Jawab HANYA dengan pertanyaannya."
)
_condense_prompt = ChatPromptTemplate.from_messages([
    ("system", _CONDENSE_SYSTEM),
    MessagesPlaceholder("history"),
    ("human", "{question}"),
])


def _is_parse_failure(e: Exception) -> bool:
    """Model reasoning (gpt-oss) kadang menghasilkan keluaran yang gagal di-parse Groq
    (error 400 'output_parse_failed'). Ini sifatnya acak, jadi aman dicoba ulang."""
    return "output_parse_failed" in str(e)


def _invoke_with_retry(chain, inputs: dict, attempts: int = 5) -> str:
    for i in range(attempts):
        try:
            return chain.invoke(inputs)
        except Exception as e:
            if _is_parse_failure(e) and i < attempts - 1:
                logger.warning("Groq output_parse_failed, coba ulang (%d/%d)", i + 1, attempts - 1)
                continue
            raise


class RetrievalEmptyError(Exception):
    """Dilempar saat tidak ada potongan dokumen yang ditemukan (collection kosong/salah nama)."""


# ----------------------------------------------------------------------------
# Fungsi bantu (diawali _ = hanya dipakai di dalam file ini)
# ----------------------------------------------------------------------------
def _format_docs(docs: list) -> str:
    """Gabungkan chunk menjadi satu teks konteks, lengkap dengan label sumbernya."""
    parts = []
    for i, doc in enumerate(docs, start=1):
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "?")
        parts.append(f"[Sumber {i} | file: {source} | hal. {page}]\n{doc.page_content}")
    return "\n\n".join(parts)


def _docs_to_sources(docs: list) -> list[dict]:
    """Ubah chunk menjadi daftar sumber untuk ditampilkan ke user (kartu sitasi)."""
    return [
        {
            "source": doc.metadata.get("source", "unknown"),
            "page": doc.metadata.get("page"),
            "snippet": doc.page_content[:250],
            "score": doc.metadata.get("score"),
        }
        for doc in docs
    ]


def _retrieve_or_raise(question: str, collection_name: str, source_filter: list[str] | None) -> list:
    """Cari chunk relevan; kalau kosong, lempar error dengan pesan yang membantu."""
    docs = retrieve_documents(
        collection_name=collection_name,
        query=question,
        k=get_settings().retrieval_k,
        source_filter=source_filter,
    )
    if not docs:
        msg = f"Tidak ada dokumen di collection '{collection_name}'."
        if source_filter:
            msg += f" Pastikan nama file {source_filter} benar."
        else:
            msg += " Upload dokumen PDF terlebih dahulu."
        raise RetrievalEmptyError(msg)
    return docs


def condense_question(question: str, history: list[BaseMessage]) -> str:
    """Jadikan pertanyaan lanjutan mandiri memakai riwayat. Tanpa riwayat -> tidak diubah
    (sekaligus menghemat 1 panggilan LLM)."""
    if not history:
        return question
    # Operator "|" menyambung langkah-langkah jadi satu "chain" (rantai):
    # prompt -> LLM -> ubah keluaran jadi teks biasa.
    chain = _condense_prompt | get_llm() | StrOutputParser()
    return _invoke_with_retry(chain, {"history": history, "question": question}).strip() or question


# ----------------------------------------------------------------------------
# 3 fungsi utama yang dipanggil router
# ----------------------------------------------------------------------------
def query_rag(question: str, collection_name: str, source_filter: list[str] | None = None) -> dict:
    """Tanya-jawab sekali putus (tanpa memori)."""
    docs = _retrieve_or_raise(question, collection_name, source_filter)  # 1. cari

    chain = _prompt | get_llm() | StrOutputParser()                      # 2+3. susun & jawab
    answer = _invoke_with_retry(chain, {"context": _format_docs(docs), "question": question})

    return {"answer": answer, "sources": _docs_to_sources(docs)}


def query_rag_conversational(
    question: str,
    collection_name: str,
    history: list[BaseMessage],
    source_filter: list[str] | None = None,
) -> dict:
    """Chat multi-turn: pertanyaan dipadatkan dulu, dicari, lalu dijawab dengan memori."""
    standalone = condense_question(question, history)
    docs = _retrieve_or_raise(standalone, collection_name, source_filter)

    chain = _chat_prompt | get_llm() | StrOutputParser()
    answer = _invoke_with_retry(chain, {
        "context": _format_docs(docs),
        "history": history,
        "question": question,  # user melihat pertanyaan aslinya; konteks dicari dgn versi mandiri
    })
    return {
        "answer": answer,
        "sources": _docs_to_sources(docs),
        "standalone_question": standalone,
    }


def prepare_conversational_stream(
    question: str,
    collection_name: str,
    history: list[BaseMessage],
    source_filter: list[str] | None = None,
):
    """Versi streaming: pencarian dilakukan dulu (butuh konteks), lalu jawaban dikirim
    potong-demi-potong lewat generator async (kata muncul satu per satu)."""
    standalone = condense_question(question, history)
    docs = _retrieve_or_raise(standalone, collection_name, source_filter)

    chain = _chat_prompt | get_llm() | StrOutputParser()
    inputs = {"context": _format_docs(docs), "history": history, "question": question}

    async def token_generator():
        # astream = versi async dari stream; setiap `chunk` adalah potongan teks jawaban.
        # Kalau gagal parse SEBELUM ada token yang terkirim, aman diulang dari awal.
        for attempt in range(5):
            sent = False
            try:
                async for chunk in chain.astream(inputs):
                    sent = True
                    yield chunk
                return
            except Exception as e:
                if _is_parse_failure(e) and not sent and attempt < 4:
                    logger.warning("Groq output_parse_failed (stream), coba ulang")
                    continue
                raise

    return token_generator(), _docs_to_sources(docs), standalone