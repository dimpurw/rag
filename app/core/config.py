"""
config.py — SEMUA pengaturan aplikasi ada di sini.

Konsep yang dipelajari: "12-factor app" — pengaturan (API key, ukuran chunk, dll)
JANGAN ditulis keras di dalam kode. Simpan di environment variable / file .env,
supaya bisa diganti tanpa mengubah kode (misal beda nilai untuk laptop vs server).
"""
import os
from functools import lru_cache

# Matikan telemetri anonim ChromaDB. Di versi yang kita pakai, telemetri ini memunculkan baris
# "Failed to send telemetry event ..." yang tampak seperti error padahal tidak berbahaya.
# Variabel ini harus diset SEBELUM client Chroma dibuat, makanya ditaruh di sini (modul yang
# pertama kali di-import).
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

# BaseSettings = class dari pydantic-settings yang otomatis membaca environment
# variable / file .env, lalu memvalidasi tipenya (str, int, dst).
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # env_file=".env"  -> baca file bernama .env di folder tempat server dijalankan
    # extra="ignore"   -> kalau .env punya variabel yang tidak kita definisikan, abaikan saja
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Aturan penamaan: field `groq_api_key` dibaca dari variabel `GROQ_API_KEY` (huruf besar).
    # Field TANPA nilai default (seperti ini) = WAJIB diisi; kalau kosong, server gagal start
    # dengan pesan jelas. Itu lebih baik daripada gagal diam-diam di tengah jalan.
    groq_api_key: str
    llm_model: str = "openai/gpt-oss-120b"

    # --- Embedding ---
    # Embedding = mengubah teks menjadi deretan angka (vektor) yang merepresentasikan MAKNA.
    # Teks bermakna mirip -> vektornya berdekatan. Inilah dasar "pencarian semantik".
    #
    # PENTING: model embedding menentukan kualitas pencarian. Model "all-MiniLM-L6-v2" hanya
    # dilatih untuk bahasa Inggris, jadi buruk untuk dokumen Indonesia. "multilingual-e5-small"
    # mendukung 100 bahasa (termasuk Indonesia) dan bisa membaca teks sampai 512 token.
    embedding_model: str = "intfloat/multilingual-e5-small"

    # --- Penyimpanan ---
    upload_dir: str = "storage/uploads"
    chroma_dir: str = "storage/chroma_db"

    # --- Chunking (memotong dokumen) ---
    # LLM & embedding tidak bisa memproses dokumen panjang sekaligus, jadi dokumen dipotong
    # jadi potongan ("chunk"). chunk_overlap = bagian yang sengaja tumpang-tindih antar chunk
    # supaya kalimat yang terpotong di perbatasan tidak kehilangan konteks.
    # Ukuran dalam KARAKTER. 1200 karakter ≈ 300-400 token, aman untuk batas 512 token model.
    chunk_size: int = 1200
    chunk_overlap: int = 200

    # --- Retrieval (pencarian) ---
    # Berapa chunk paling relevan yang diambil untuk dijadikan konteks bagi LLM.
    # Terlalu kecil -> info penting terlewat. Terlalu besar -> LLM kebanjiran info tak relevan.
    retrieval_k: int = 10

    # --- Web / keamanan ---
    allowed_origins: str = "http://localhost:3000"  # daftar domain frontend yang boleh memanggil API (CORS)
    rate_limit_per_minute: int = 20
    max_upload_size_mb: int = 20
    api_key: str | None = None  # `| None = None` artinya opsional; kosong = auth nonaktif

    # --- Memori percakapan ---
    max_history_turns: int = 5  # berapa giliran tanya-jawab terakhir yang diingat

    # --- Aplikasi ---
    app_env: str = "development"
    log_level: str = "INFO"

    @property
    def allowed_origins_list(self) -> list[str]:
        """Ubah string 'a.com,b.com' dari .env menjadi list ['a.com', 'b.com']."""
        if self.allowed_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


# @lru_cache = hasil fungsi disimpan setelah pemanggilan pertama.
# Jadi file .env hanya dibaca SEKALI, lalu semua bagian aplikasi memakai objek yang sama.
@lru_cache
def get_settings() -> Settings:
    return Settings()