# Panduan Penggunaan — RAG API (LangChain + Groq + Chroma)

Panduan ini menjelaskan cara pakai API dari nol: setup, jalankan server, sampai contoh lengkap semua endpoint.

---

## ⚠️ Sudah Pernah Install Versi Sebelumnya? Lakukan Ini Dulu

Versi ini mengganti model embedding menjadi **multilingual** (agar dokumen berbahasa Indonesia dicari dengan benar).
File `.env` lama Anda **menimpa** nilai default di kode, jadi ubah dulu:

1. Buka file `.env`, cari lalu ganti (atau tambahkan) tiga baris ini:
   ```env
   EMBEDDING_MODEL=intfloat/multilingual-e5-small
   CHUNK_SIZE=1200
   RETRIEVAL_K=6
   ```
2. Restart server.
3. **Upload ulang PDF Anda.** Database lama tidak dipakai lagi (vektor model lama tidak cocok dengan model baru),
   jadi folder `storage/chroma_db/` yang lama boleh dihapus.
4. Saat pertama kali upload, model embedding (±470 MB) diunduh otomatis — butuh internet dan beberapa menit. Hanya sekali.

---

## Langkah 1 — Dapatkan API Key Groq (Gratis)

1. Buka https://console.groq.com
2. Daftar/login (bisa pakai akun Google)
3. Masuk ke menu **API Keys** → klik **Create API Key**
4. Salin key yang muncul (formatnya `gsk_...`) — ini hanya muncul sekali, simpan baik-baik

---

## Langkah 2 — Setup Project

Extract file `rag-backend.zip`, lalu buka terminal di folder tersebut.

```bash
cd rag-backend
cp .env.example .env
```

Buka file `.env`, isi minimal bagian ini:
```env
GROQ_API_KEY=gsk_isi_dengan_key_asli_anda
API_KEY=
```
`API_KEY` boleh dikosongkan dulu untuk latihan (auth nonaktif). Isi nanti kalau mau simulasi production.

---

## Langkah 3 — Jalankan Server

**Opsi A — Docker (disarankan):**
```bash
docker compose up -d --build
```

**Opsi B — Manual (Python):**
```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Cek server sudah hidup:
```bash
curl http://localhost:8000/health
# {"status":"ok","env":"development"}
```

Buka juga **http://localhost:8000/docs** — dokumentasi interaktif, bisa coba semua endpoint langsung dari browser tanpa curl.

---

## Langkah 4 (Tercepat) — Coba Lewat Demo Frontend

Daripada pakai curl satu-satu, buka saja halaman chat siap pakai di browser:

```
http://localhost:8000/demo/
```

Di halaman ini Anda bisa: upload PDF (drag & drop), lihat daftar dokumen yang ter-index, chat dengan jawaban streaming real-time, dan lihat sumber kutipan tiap jawaban — semua tanpa perlu terminal. Cocok dipakai untuk demo langsung ke orang lain atau rekam layar untuk portofolio.

Lanjutkan ke bagian di bawah kalau ingin memahami cara kerja tiap endpoint API secara detail (misalnya untuk integrasi ke aplikasi Anda sendiri).

---

## Langkah 4b — Upload Dokumen (via API langsung)

Upload PDF ke sebuah "collection" (namespace bebas Anda beri nama sendiri):

```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@contoh-laporan-tahunan-PT-Nusantara-Digital.pdf" \
  -F "collection=laporan_tahunan"
```

Response:
```json
{
  "filename": "contoh-laporan-tahunan-PT-Nusantara-Digital.pdf",
  "collection": "laporan_tahunan",
  "num_chunks": 8,
  "num_pages": 2,
  "message": "Dokumen berhasil diproses dan diindex."
}
```

> Bisa upload berkali-kali ke collection yang sama untuk gabungkan banyak dokumen (lihat Langkah 7).

---

## Langkah 5 — Tanya Jawab Sekali Putus (`/query`)

Cocok untuk pertanyaan mandiri tanpa perlu diingat riwayatnya.

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Berapa pertumbuhan laba bersih tahun 2025?",
    "collection": "laporan_tahunan"
  }'
```

Response:
```json
{
  "answer": "Laba bersih tahun 2025 tumbuh 41,2% dibanding 2024, dari Rp 292 miliar menjadi Rp 412 miliar.",
  "sources": [
    {"source": "contoh-laporan-tahunan-...pdf", "page": 1, "snippet": "..."}
  ]
}
```

---

## Langkah 6 — Chat Multi-turn (`/chat`) — Ada Memory

Cocok untuk percakapan berkelanjutan. Wajib sertakan `session_id` (bebas, misal UUID atau ID user).

```bash
# Giliran 1
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo-1",
    "question": "Berapa total pendapatan tahun 2025?",
    "collection": "laporan_tahunan"
  }'

# Giliran 2 — merujuk jawaban sebelumnya tanpa perlu sebut ulang detail
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo-1",
    "question": "Bagaimana dibanding tahun sebelumnya?",
    "collection": "laporan_tahunan"
  }'
```

Response menyertakan `standalone_question` — versi "dipadatkan" dari pertanyaan giliran ke-2 (mis. jadi "Berapa pendapatan 2024 dibanding 2025?"), berguna untuk debugging.

Hapus riwayat kalau mau mulai obrolan baru:
```bash
curl -X DELETE http://localhost:8000/api/v1/chat/demo-1
```

---

## Langkah 7 — Multi-dokumen dalam Satu Collection

Upload dokumen kedua ke collection yang sama:
```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@laporan-2024.pdf" \
  -F "collection=laporan_tahunan"
```

Cek file apa saja yang sudah ada di collection itu:
```bash
curl http://localhost:8000/api/v1/collections/laporan_tahunan/documents
# {"collection":"laporan_tahunan","documents":["contoh-laporan-...pdf","laporan-2024.pdf"]}
```

Tanya ke **satu file spesifik saja** pakai `source_filter` (nama harus persis seperti hasil di atas):
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Berapa pendapatan tahun ini?",
    "collection": "laporan_tahunan",
    "source_filter": ["laporan-2024.pdf"]
  }'
```
Kosongkan `source_filter` untuk mencari di seluruh dokumen dalam collection.

---

## Langkah 8 — Streaming Jawaban (`/chat/stream`)

Untuk frontend yang mau menampilkan jawaban muncul kata-per-kata (real-time), bukan menunggu selesai.

```bash
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo-1",
    "question": "Ringkas isi dokumen ini",
    "collection": "laporan_tahunan"
  }'
```
(`-N` di curl penting supaya output tidak di-buffer, langsung tampil per baris)

Output berupa Server-Sent Events, tiap baris `data: {...}`:
```
data: {"token": "Perusahaan"}
data: {"token": " mencatat"}
data: {"token": " pertumbuhan"}
...
data: {"done": true, "sources": [...], "standalone_question": "..."}
```

Kalau dipakai dari JavaScript (frontend), gunakan `EventSource` atau `fetch` dengan reader stream — bukan `curl`.

---

## Langkah 9 — Kelola Collection

Lihat semua collection yang ada:
```bash
curl http://localhost:8000/api/v1/collections
```

Hapus collection beserta seluruh isinya:
```bash
curl -X DELETE http://localhost:8000/api/v1/collections/laporan_tahunan
```

---

## Langkah 10 — Aktifkan API Key (Simulasi Production)

Edit `.env`:
```env
API_KEY=rahasia-saya-123
```
Restart server, lalu semua endpoint `/api/v1/*` wajib sertakan header:
```bash
curl http://localhost:8000/api/v1/collections \
  -H "X-API-Key: rahasia-saya-123"
```
Tanpa header ini akan dapat error `401 Unauthorized`. Endpoint `/health` tetap bisa diakses tanpa key.

---

## Ringkasan Semua Endpoint

| Endpoint | Method | Fungsi | Butuh Session? |
|---|---|---|---|
| `/health` | GET | Cek server hidup | Tidak |
| `/api/v1/upload` | POST | Upload PDF ke collection | Tidak |
| `/api/v1/query` | POST | Tanya jawab sekali putus | Tidak |
| `/api/v1/chat` | POST | Tanya jawab dengan memory | Ya (`session_id`) |
| `/api/v1/chat/stream` | POST | Sama seperti `/chat`, tapi streaming | Ya (`session_id`) |
| `/api/v1/chat/{session_id}` | DELETE | Hapus riwayat percakapan | Ya |
| `/api/v1/collections` | GET | List semua collection | Tidak |
| `/api/v1/collections/{name}/documents` | GET | List file dalam collection | Tidak |
| `/api/v1/collections/{name}/documents/{filename}` | DELETE | Hapus satu file spesifik | Tidak |
| `/api/v1/collections/{name}` | DELETE | Hapus collection | Tidak |
| `/demo/` | GET | Halaman chat interaktif (browser) | Tidak |

---

## Troubleshooting Umum

| Masalah | Penyebab | Solusi |
|---|---|---|
| `404 Tidak ditemukan dokumen relevan` | Collection kosong / salah nama | Cek `GET /api/v1/collections`, pastikan sudah upload |
| `401 Unauthorized` | `API_KEY` di `.env` diisi tapi header tidak disertakan | Tambahkan header `X-API-Key` |
| `422 Unprocessable Entity` | Format request salah (field kosong, terlalu panjang) | Cek pesan error, biasanya sudah jelas field mana yang salah |
| `413 File terlalu besar` | PDF melebihi `MAX_UPLOAD_SIZE_MB` | Perbesar limit di `.env`, atau kompres PDF |
| Jawaban tidak relevan / asal | PDF hasil scan gambar (bukan teks asli) | Perlu OCR dulu (belum didukung versi ini) |
| Server lambat pertama kali dipakai | Model embedding baru pertama kali di-download | Normal, hanya terjadi sekali (lalu ter-cache) |
| Jawaban tidak sesuai isi PDF | Model embedding lama (khusus Inggris) atau database lama masih terpakai | Ikuti bagian "Sudah Pernah Install Versi Sebelumnya?" di atas, lalu upload ulang PDF |
| Halaman di sitasi berbeda 1 dari PDF | Versi lama menghitung halaman dari 0 | Sudah diperbaiki; upload ulang PDF agar nomor halaman benar |
| Error `page_content ... NoneType` | Ada baris rusak di database lama | Sudah ditangani otomatis (baris rusak dilewati); atau hapus collection lalu upload ulang |
| Notifikasi "Batas pemakaian gratis Groq tercapai" | Free tier Groq kena limit per menit | Tunggu ±1 menit lalu ulangi |
| Notifikasi "Tidak bisa terhubung ke server" | Server tidak berjalan / alamat API Base URL salah | Jalankan server, cek kolom "API Base URL" di sidebar demo |
| Upload pertama sangat lama | Model embedding sedang diunduh | Normal, hanya sekali |
