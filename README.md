# RAG API — LangChain + Groq + Chroma (100% Gratis)

Backend production-ready untuk **tanya-jawab dokumen PDF** (Retrieval Augmented Generation) menggunakan LangChain.

## Stack
| Komponen | Teknologi | Biaya |
|---|---|---|
| Framework API | FastAPI | Gratis |
| LLM | Groq (Llama 3.3 70B) | Gratis (free tier) |
| Embedding | HuggingFace `multilingual-e5-small` (lokal, mendukung bahasa Indonesia) | Gratis, tanpa API key |
| Vector DB | ChromaDB (self-hosted) | Gratis |
| Orkestrasi | LangChain | Gratis |

Satu-satunya yang perlu didaftar adalah **API key Groq gratis** di https://console.groq.com

## Halaman Web Siap Pakai

Setelah server jalan, tiga halaman ini otomatis tersedia (tidak perlu setup tambahan):

| Halaman | URL | Fungsi |
|---|---|---|
| **Landing Page** | `/` | Halaman marketing produk — cocok untuk pertama kali diperlihatkan |
| **Demo Console** | `/demo/` | Chat interaktif dengan streaming, upload PDF, citation |
| **Usage Dashboard** | `/dashboard/` | Statistik pemakaian real-time (total upload, query, latency) |
| **API Docs** | `/docs` | Swagger UI — dokumentasi interaktif seluruh endpoint |

Panduan pemakaian ada di **`USAGE.md`**, penjelasan setiap kode (untuk belajar) ada di **`BELAJAR.md`**. Kalau ingin upload project ini ke GitHub (misal untuk portofolio), ikuti **`GITHUB_UPLOAD.md`**.

---

## 1. Setup Lokal (tanpa Docker)

```bash
# 1. Buat virtual environment
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install dependency
pip install -r requirements.txt

# 3. Copy env file dan isi API key
cp .env.example .env
# Edit .env, isi GROQ_API_KEY dengan key dari console.groq.com

# 4. Jalankan server
uvicorn app.main:app --reload --port 8000
```

Buka **http://localhost:8000/docs** untuk dokumentasi interaktif (Swagger UI).

---

## 2. Setup dengan Docker (Rekomendasi untuk Production)

```bash
cp .env.example .env
# Edit .env, isi GROQ_API_KEY

docker compose up -d --build
```

Server berjalan di `http://localhost:8000`, dengan data Chroma & upload tersimpan permanen di Docker volume.

---

## 3. Cara Pakai API

### Upload dokumen PDF
```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@dokumen.pdf" \
  -F "collection=produk_saya"
```

### Tanya jawab berdasarkan dokumen
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Apa isi utama dokumen ini?", "collection": "produk_saya"}'
```

### Tanya jawab dengan filter ke file tertentu (multi-dokumen)
Satu collection bisa berisi banyak PDF sekaligus (upload berkali-kali ke collection yang sama).
Untuk membatasi pencarian hanya ke file tertentu, gunakan `source_filter` (isi nama file persis seperti saat upload):
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Berapa pendapatan tahun ini?",
    "collection": "laporan_tahunan",
    "source_filter": ["laporan-2025.pdf"]
  }'
```
Bisa juga isi beberapa file sekaligus di `source_filter` (misal bandingkan 2 dokumen spesifik, abaikan dokumen lain di collection yang sama). Kosongkan/hapus field ini untuk mencari di seluruh dokumen dalam collection.

### Lihat semua collection
```bash
curl http://localhost:8000/api/v1/collections
```

### Lihat semua file dalam satu collection
Berguna untuk tahu nama file persis yang bisa dipakai di `source_filter`.
```bash
curl http://localhost:8000/api/v1/collections/laporan_tahunan/documents
```

### Hapus collection
```bash
curl -X DELETE http://localhost:8000/api/v1/collections/produk_saya
```

### Health check
```bash
curl http://localhost:8000/health
```

---

## 4. Fitur Pro (Baru)

### Autentikasi API Key
Set `API_KEY` di `.env` untuk mengaktifkan proteksi. Jika kosong, auth nonaktif (mode development).
Endpoint `/health` dan `/` tetap publik (untuk keperluan monitoring/load balancer); semua endpoint `/api/v1/*` butuh header:
```bash
curl http://localhost:8000/api/v1/collections -H "X-API-Key: your_secret_key"
```

### Chat Multi-turn (RAG dengan Memory)
Endpoint `/api/v1/chat` mengingat riwayat percakapan per `session_id`, sehingga pertanyaan lanjutan yang merujuk konteks sebelumnya (mis. "kalau dibanding tahun lalu?", "jelaskan lebih detail") bisa dipahami tanpa mengulang konteksnya secara eksplisit. Di balik layar, pertanyaan lanjutan otomatis "dipadatkan" (condensed) menjadi pertanyaan mandiri sebelum retrieval.

```bash
# Turn 1
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "user-123", "question": "Berapa pendapatan tahun 2025?", "collection": "laporan_tahunan"}'

# Turn 2 - merujuk konteks turn sebelumnya, tanpa perlu sebut "pendapatan" lagi
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "user-123", "question": "Bagaimana kalau dibanding tahun sebelumnya?", "collection": "laporan_tahunan"}'
```

Response berisi `standalone_question` — pertanyaan mandiri hasil condense, berguna untuk transparansi/debugging.

Hapus riwayat percakapan suatu session:
```bash
curl -X DELETE http://localhost:8000/api/v1/chat/user-123
```

> Catatan: riwayat disimpan in-memory per proses (cocok untuk demo/single-instance). Untuk production multi-instance atau butuh persistensi antar-restart, ganti implementasi di `app/services/chat_history.py` dengan Redis atau database.

### Streaming Response (Server-Sent Events)
Endpoint `/api/v1/chat/stream` mengirim jawaban token-by-token secara real-time (seperti ChatGPT), bukan menunggu jawaban lengkap selesai.

```bash
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"session_id": "user-123", "question": "Ringkas isi dokumen ini", "collection": "laporan_tahunan"}'
```

Format output tiap baris adalah SSE (`data: {...}`), berisi `{"token": "..."}` per potongan teks, diakhiri dengan `{"done": true, "sources": [...], "standalone_question": "..."}`.

### Automated Testing
```bash
pip install -r requirements.txt
pytest -v
```
22 test mencakup: health check, validasi input, endpoint RAG (dengan mocking, tanpa perlu API key/network asli), proteksi API key, chat history service, dan CRUD dokumen.

### CI/CD Otomatis (GitHub Actions)
Setiap push/PR ke `main`/`master` otomatis menjalankan seluruh test suite di 2 versi Python (3.11 & 3.12). Lihat `.github/workflows/ci.yml`. Cukup push repo ini ke GitHub, workflow langsung aktif tanpa setup tambahan.

### Demo Frontend (Halaman Chat Interaktif)
Halaman chat siap pakai untuk testing manual/demo, tanpa perlu curl atau Postman. Otomatis ter-serve begitu server jalan:

```
http://localhost:8000/demo/
```

Fitur halaman ini: upload PDF drag-and-drop, lihat daftar dokumen ter-index, chat dengan streaming real-time (token muncul satu-satu), tampilan sumber kutipan per jawaban, dan reset session. Cocok untuk direkam/screenshot sebagai bahan portofolio.

### Hapus Dokumen Spesifik (bukan seluruh collection)
```bash
curl -X DELETE http://localhost:8000/api/v1/collections/laporan_tahunan/documents/laporan-2024.pdf
```
Hanya menghapus chunk milik file tersebut, dokumen lain dalam collection yang sama tetap utuh.

### Request Tracing
Setiap response menyertakan header `X-Request-ID` (bisa dikirim sendiri via header yang sama untuk korelasi lintas layanan). ID ini juga muncul di log server dan di body error 500, memudahkan pelacakan saat debugging production.

### Landing Page
Halaman marketing di `/` — hero section, feature grid, diagram "cara kerja", dan daftar stack teknologi. Dipakai sebagai first impression sebelum orang masuk ke demo console. Semua styling berbagi satu file `static/assets/theme.css` dengan halaman demo & dashboard, supaya konsisten.

### Usage Dashboard
Halaman `/dashboard/` menampilkan statistik pemakaian real-time: total dokumen ter-upload, total query, total pesan chat, uptime server, rata-rata response time, dan error rate — auto-refresh tiap 5 detik. Datanya diambil dari endpoint publik:
```bash
curl http://localhost:8000/api/v1/metrics
```
Endpoint ini sengaja tidak butuh API key (supaya bisa ditampilkan di dashboard/landing page sebagai "live stats"). Kalau data pemakaian Anda sensitif, tambahkan proteksi tersendiri untuk endpoint ini.

---

## 5. Struktur Proyek

```
app/
├── main.py                 # Entrypoint FastAPI, middleware, CORS, rate limit, serve halaman statis
├── core/
│   ├── config.py             # Konfigurasi via environment variable
│   ├── logging_config.py     # Setup logging terstruktur
│   └── security.py           # Dependency verifikasi API key
├── models/
│   └── schemas.py            # Pydantic request/response schemas
├── routers/
│   └── rag.py                 # Endpoint upload, query, chat, streaming, collections
└── services/
    ├── model_provider.py     # Load LLM (Groq) & embedding (HuggingFace), di-cache
    ├── vector_store.py        # Wrapper ChromaDB per-collection
    ├── ingestion.py           # Load PDF -> split -> embed -> index
    ├── rag_chain.py            # Retrieval + prompt + generation (single-turn & multi-turn)
    ├── chat_history.py         # Penyimpanan riwayat percakapan in-memory per session
    └── metrics.py              # Counter & latency in-memory untuk usage dashboard
static/
├── landing.html               # Halaman marketing (served di /)
├── demo.html                  # Demo console chat interaktif (served di /demo/)
├── dashboard.html              # Usage dashboard (served di /dashboard/)
└── assets/theme.css            # Design system bersama (dipakai ketiga halaman di atas)
tests/
├── conftest.py                # Fixture pytest (TestClient)
├── test_health.py              # Test endpoint health/root/openapi/halaman statis
├── test_validation.py          # Test validasi input
├── test_rag_endpoints_mocked.py   # Test endpoint RAG dengan mocking
├── test_security.py            # Test dependency API key
└── test_chat_history.py        # Test service riwayat percakapan
```

## 6. Fitur Production-Ready
- ✅ Autentikasi API key (opsional, via header `X-API-Key`)
- ✅ Chat multi-turn dengan memory percakapan per session
- ✅ Streaming response (Server-Sent Events)
- ✅ Demo frontend siap pakai (`/demo`) — chat UI dengan upload, streaming, dan citation
- ✅ Request tracing (`X-Request-ID` di tiap response & log)
- ✅ CI/CD otomatis (GitHub Actions — test jalan tiap push/PR)
- ✅ Automated test suite (pytest, 22 test, mocking tanpa perlu API key/network asli)
- ✅ Rate limiting per-IP (`slowapi`) — default 10 upload/menit, 20-30 query-chat/menit
- ✅ Validasi input ketat (tipe file, ukuran file, panjang pertanyaan)
- ✅ Error handling terstruktur (tidak pernah bocor stack trace ke client)
- ✅ Logging request/response dengan durasi
- ✅ CORS dikonfigurasi via env (bisa dibatasi ke domain frontend tertentu)
- ✅ Model di-cache (`lru_cache`) agar tidak reload setiap request
- ✅ Multi-collection — bisa index banyak dokumen terpisah dengan namespace berbeda
- ✅ Multi-dokumen per collection — satu collection bisa berisi banyak PDF, dengan opsi filter pencarian ke file tertentu (`source_filter`) atau ke seluruh dokumen dalam collection
- ✅ CRUD dokumen lengkap — hapus satu file spesifik atau seluruh collection
- ✅ Dockerfile dengan non-root user & healthcheck
- ✅ Data persisten via Docker volume (Chroma tidak hilang saat restart)
- ✅ Konfigurasi 100% via environment variable (12-factor app)

## 7. Catatan Scaling
- Untuk trafik tinggi, ganti Chroma lokal dengan **Chroma Server mode** atau vector DB terkelola (Qdrant Cloud/Pinecone free tier).
- Untuk multi-instance/horizontal scaling, `storage/chroma_db` perlu di-mount ke shared volume/network storage, atau pindah ke vector DB terpisah (bukan embedded).
- Riwayat percakapan (`chat_history.py`) saat ini in-memory per proses — untuk multi-instance, ganti ke Redis agar session konsisten di semua instance.
- Tambahkan reverse proxy (Nginx/Caddy) + HTTPS di depan container untuk deployment publik.
- **Jangan menambah `--workers` selama masih memakai ChromaDB embedded.** Indeks pencarian Chroma ada di memori tiap proses: dokumen yang diupload lewat satu worker tidak terlihat oleh worker lain (pencarian kosong / jawaban tidak sesuai PDF). Riwayat chat dan statistik dashboard juga per proses. Untuk menambah worker, pindahkan dulu ke vector DB server (Chroma server/Qdrant) dan Redis.

## 8. Batas Free Tier yang Perlu Diketahui
- **Groq**: free tier punya limit request/token per menit (cek dashboard console.groq.com untuk angka terbaru). Cukup untuk development & trafik kecil-menengah.
- **HuggingFace embedding lokal**: tidak ada limit karena jalan di server sendiri, tapi butuh RAM (~500MB-1GB) dan CPU saat pertama kali load model.
