FROM python:3.11-slim

WORKDIR /app

# Dependency sistem minimal untuk build package (misal chromadb/sentence-transformers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY static ./static

RUN mkdir -p storage/uploads storage/chroma_db

# User non-root untuk keamanan
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# PENTING: jalankan HANYA 1 proses (jangan tambah --workers).
# ChromaDB versi embedded menyimpan indeks pencariannya di memori tiap proses. Kalau ada 2+ worker,
# dokumen yang diupload lewat worker A TIDAK terlihat oleh worker B (pencarian kosong / jawaban tidak
# sesuai PDF). Riwayat chat dan statistik dashboard juga disimpan per proses, jadi ikut tercecer.
# Untuk skala lebih besar: pindah ke vector DB server (Chroma server / Qdrant) + Redis, baru tambah worker.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
