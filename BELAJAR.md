# Panduan Belajar — Memahami Kode RAG API dari Nol

Panduan ini menjelaskan **setiap bagian kode** di proyek ini, urut sesuai jalannya data, dengan bahasa
sederhana. Cocok kalau Anda baru belajar Python/backend/AI. Kode aslinya juga sudah diberi komentar
penjelasan; panduan ini adalah "peta besar"-nya.

**Cara membaca yang disarankan:** baca bagian 1-3 dulu (konsep), lalu buka file kodenya
berdampingan dengan bagian 4 sambil membaca. Setelah itu kerjakan latihan di bagian 7.

---

## 1. Gambaran Besar: Apa yang Sebenarnya Terjadi?

Model AI seperti ChatGPT/Llama tidak tahu isi PDF Anda. Kita tidak bisa menempelkan seluruh PDF ke
dalam prompt (terlalu panjang, mahal, dan lambat). Solusinya **RAG (Retrieval-Augmented Generation)**:
*cari dulu potongan yang relevan, baru minta AI menjawab dari potongan itu.*

### Alur 1 — UPLOAD (dilakukan sekali per dokumen)

```
 PDF  ──►  baca teks   ──►  potong jadi   ──►  ubah tiap potongan   ──►  simpan di
          per halaman      chunk (±1200       jadi VEKTOR (deretan       database vektor
          (PyPDFLoader)    karakter)          angka pembawa makna)       (ChromaDB)
          ingestion.py     ingestion.py       model_provider.py          vector_store.py
```

### Alur 2 — BERTANYA (setiap kali user mengetik pertanyaan)

```
 Pertanyaan ──► ubah jadi ──► cari chunk dengan ──► susun PROMPT:        ──► LLM (Groq)  ──► Jawaban
 "Berapa laba   VEKTOR        vektor TERDEKAT        aturan + chunk          menulis         + sumber
  bersih?"      (embedding)   (top-k = 6 chunk)      + pertanyaan            jawaban         (halaman)
                              vector_store.py        rag_chain.py            rag_chain.py
```

**Inti yang harus dipahami:** kualitas jawaban ditentukan oleh DUA tahap yang terpisah:
1. **Retrieval** — apakah chunk yang ditemukan benar-benar berisi jawabannya?
2. **Generation** — apakah LLM menulis jawaban dengan setia dari chunk itu?

Jika jawaban salah, hampir selalu masalahnya ada di tahap 1 (chunk yang diambil keliru).
Lihat bagian 6 untuk cara memeriksanya.

---

## 2. Glosarium Istilah

| Istilah | Arti sederhana |
|---|---|
| **API** | "Pintu" program: program lain (atau halaman web) mengirim permintaan ke alamat tertentu lalu menerima jawaban. |
| **Endpoint** | Satu alamat di API, misalnya `POST /api/v1/upload`. |
| **FastAPI** | Library Python untuk membuat API. |
| **LLM** | Large Language Model — AI penulis teks (di sini Llama 3.3 lewat layanan Groq). |
| **Prompt** | Teks instruksi + data yang kita kirim ke LLM. |
| **Embedding** | Mengubah teks menjadi deretan angka yang mewakili *makna*. Teks bermakna mirip → angkanya berdekatan. |
| **Vektor** | Deretan angka hasil embedding (di sini 384 angka per potongan teks). |
| **Vector store / vector DB** | Database yang pandai mencari vektor terdekat. Kita pakai ChromaDB. |
| **Chunk** | Potongan kecil dokumen (satu baris di database vektor). |
| **Collection** | "Folder" di database vektor. Satu collection bisa berisi banyak PDF. |
| **Retrieval / top-k** | Mengambil *k* chunk paling relevan (k = `RETRIEVAL_K`). |
| **Metadata** | Label tambahan pada chunk: nama file, nomor halaman, dst. |
| **Token** | Satuan potongan kata yang dipakai LLM (±3-4 karakter). |
| **Streaming / SSE** | Jawaban dikirim sedikit-sedikit (kata demi kata), bukan menunggu selesai semua. |
| **Middleware** | Kode yang "mencegat" setiap request sebelum/sesudah diproses (untuk logging, CORS, dll). |
| **Dependency (FastAPI)** | Fungsi yang dijalankan otomatis sebelum endpoint (contoh: cek API key). |
| **Rate limit** | Batas jumlah request per menit agar server tidak kebanjiran. |
| **CORS** | Aturan browser: domain mana yang boleh memanggil API ini. |
| **Environment variable / `.env`** | Pengaturan di luar kode (API key, ukuran chunk) supaya mudah diganti. |

---

## 3. Peta Folder

```
rag-backend/
├── app/
│   ├── main.py                  ← pintu masuk aplikasi: menyalakan FastAPI, middleware, halaman web
│   ├── core/
│   │   ├── config.py            ← semua pengaturan (dibaca dari .env)
│   │   ├── security.py          ← pengecekan API key
│   │   └── logging_config.py    ← format catatan log di terminal
│   ├── models/schemas.py        ← bentuk data request & response (validasi otomatis)
│   ├── routers/rag.py           ← daftar endpoint (upload, query, chat, dst)
│   └── services/                ← "otak" aplikasi
│       ├── model_provider.py    ← membuat model embedding & LLM
│       ├── ingestion.py         ← proses upload PDF
│       ├── vector_store.py      ← baca/tulis/cari di ChromaDB
│       ├── rag_chain.py         ← INTI RAG: cari + prompt + jawab
│       ├── chat_history.py      ← memori percakapan
│       └── metrics.py           ← statistik untuk dashboard
├── static/                      ← halaman web: landing.html, demo.html, dashboard.html
├── tests/                       ← tes otomatis (pytest)
├── Dockerfile, docker-compose.yml, .github/workflows/ci.yml
└── .env (rahasia, tidak di-upload ke GitHub)
```

**Prinsip desain yang dipakai:** pemisahan tanggung jawab.
`routers/` hanya mengurus "menerima & menjawab HTTP", sedangkan logika sebenarnya ada di `services/`.
Dengan begitu logika bisa dites/diubah tanpa menyentuh urusan web.

---

## 4. Penjelasan File Satu per Satu

### 4.1 `requirements.txt` — daftar library

Berisi library Python yang dibutuhkan beserta versinya (`fastapi==0.115.6`). Versi dikunci agar
proyek berjalan sama di laptop Anda, server, dan CI. Install semuanya dengan
`pip install -r requirements.txt`. Library utama:

| Library | Fungsi |
|---|---|
| `fastapi`, `uvicorn` | membuat API dan menjalankannya sebagai server |
| `langchain-*` | perekat: loader PDF, text splitter, prompt, rantai (chain) |
| `langchain-groq` | menyambung ke LLM Groq |
| `sentence-transformers`, `langchain-huggingface` | menjalankan model embedding di komputer sendiri |
| `chromadb`, `langchain-chroma` | database vektor |
| `pypdf` | membaca teks dari PDF |
| `slowapi` | rate limiting |
| `pydantic`, `pydantic-settings` | validasi data & pembacaan `.env` |
| `pytest`, `httpx` | tes otomatis |

### 4.2 `app/core/config.py` — pusat pengaturan

```python
class Settings(BaseSettings):
    groq_api_key: str                       # TANPA default → wajib diisi di .env
    embedding_model: str = "intfloat/multilingual-e5-small"
    chunk_size: int = 1200
    retrieval_k: int = 6
```

- `BaseSettings` otomatis membaca environment variable/`.env`. Field `chunk_size` dibaca dari
  variabel `CHUNK_SIZE`.
- Nilai setelah `=` adalah **default**; nilai di `.env` **menimpa** default.
  ⚠️ Ini sering membingungkan: kalau `.env` Anda masih berisi nilai lama, nilai baru di `config.py`
  tidak akan terpakai.
- `@lru_cache` pada `get_settings()` membuat `.env` hanya dibaca sekali.

### 4.3 `app/services/model_provider.py` — membuat model AI

Dua fungsi: `get_embeddings()` dan `get_llm()`, keduanya `@lru_cache` karena memuat model itu mahal.

**Embedding & kenapa memilih model multilingual.** Model embedding "belajar" makna dari data
latihannya. `all-MiniLM-L6-v2` dilatih untuk bahasa Inggris, sehingga untuk teks Indonesia
vektornya kurang bermakna → chunk yang ditemukan sering salah → jawaban meleset dari PDF.
`multilingual-e5-small` dilatih untuk banyak bahasa termasuk Indonesia.

**Kenapa ada `PrefixedEmbeddings`?** Model E5 dilatih dengan aturan: dokumen diawali `"passage: "`,
pertanyaan diawali `"query: "`. Class turunan ini menambahkan awalan itu otomatis:

```python
class PrefixedEmbeddings(HuggingFaceEmbeddings):          # mewarisi semua fitur class induk
    def embed_query(self, text):                           # dipanggil saat BERTANYA
        return super().embed_query(self.query_prefix + text)
    def embed_documents(self, texts):                      # dipanggil saat UPLOAD
        return super().embed_documents([self.doc_prefix + t for t in texts])
```

**LLM:** `ChatGroq(..., temperature=0.1)`. *Temperature* mengatur kreativitas; nilai rendah membuat
jawaban konsisten dan setia pada fakta, cocok untuk tanya-jawab dokumen.

### 4.4 `app/services/ingestion.py` — alur upload PDF

Fungsi `ingest_pdf` bekerja dalam 5 langkah (sesuai komentar di kode):

1. `PyPDFLoader(file_path).load()` → satu `Document` per halaman.
2. `RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200)` → memotong teks. Ia mencoba
   memotong di paragraf dulu, lalu baris, kalimat, kata. `chunk_overlap` membuat potongan saling
   tumpang-tindih 200 karakter agar kalimat di perbatasan tidak kehilangan konteks.
3. Buang chunk kosong (`if c.page_content and c.page_content.strip()`) — PDF hasil scan tidak
   punya teks, dan chunk kosong di database nanti memicu error.
4. Lengkapi metadata. Baris penting:
   ```python
   chunk.metadata["page"] = int(chunk.metadata.get("page", 0)) + 1
   ```
   PyPDF menghitung halaman dari 0, manusia dari 1. Tanpa `+ 1`, sitasi "hal. 1" sebenarnya halaman 2.
5. `store.add_documents(...)` → hitung vektor tiap chunk (memanggil model embedding) lalu simpan.

`save_upload_file` menyimpan file sementara ke disk. `os.path.basename(filename)` mencegah serangan
*path traversal* (nama file jahat seperti `../../rahasia`).

### 4.5 `app/services/vector_store.py` — database vektor

**`_persist_dir()`** — folder database dipisah per model embedding
(`storage/chroma_db/intfloat_multilingual-e5-small/`). Vektor dari model berbeda tidak bisa
dibandingkan; kalau tercampur, pencarian jadi ngawur. Dengan memisahkan folder, mengganti model
otomatis memakai database baru yang bersih (konsekuensinya: PDF harus di-upload ulang).

**`get_vector_store()`** — membuka satu collection. `collection_metadata={"hnsw:space": "cosine"}`
memakai jarak cosine (ukuran sudut antar vektor), standar untuk teks.

**`retrieve_documents()`** — fungsi pencarian utama:

```python
query_vector = get_embeddings().embed_query(query)            # 1. pertanyaan → vektor
result = store._collection.query(query_embeddings=[query_vector], n_results=..., where=...)  # 2. cari terdekat
...
if not text or not text.strip():                              # 3. lewati baris rusak
    continue
metadata["score"] = round(max(0.0, 1.0 - float(dist)), 3)     # 4. skor kemiripan 0-1
```

Kenapa tidak memakai `as_retriever()` bawaan LangChain? Bila ada baris di database yang isi teksnya
kosong (`None`), LangChain langsung *crash* dengan error
`1 validation error for Document page_content ... NoneType`. Dengan memanggil Chroma langsung,
baris rusak kita lewati dan pencarian tetap berjalan.

`where` adalah filter metadata (misal hanya cari di file tertentu): `{"source": "laporan.pdf"}`
atau `{"source": {"$in": [...]}}` untuk beberapa file.

Fungsi lain: `list_documents_in_collection` (daftar file unik), `list_collections`
(memakai client Chroma langsung supaya tidak membuat collection palsu "langchain"),
`delete_document_from_collection`, `delete_collection`.

### 4.6 `app/services/rag_chain.py` — inti RAG

**Prompt** (`SYSTEM_PROMPT`) berisi aturan untuk LLM: jawab hanya dari konteks, kutip angka persis,
perhatikan urutan kolom tabel, katakan "tidak ditemukan" jika tidak ada. Prompt adalah tempat paling
murah untuk memperbaiki perilaku jawaban.

`{context}` dan `{question}` adalah "lubang" yang diisi saat dijalankan.

**Chain** — operator `|` menyambung langkah menjadi satu rantai:

```python
chain = _prompt | get_llm() | StrOutputParser()
answer = chain.invoke({"context": _format_docs(docs), "question": question})
```
Artinya: isi prompt → kirim ke LLM → ambil hasilnya sebagai teks biasa.

**Tiga fungsi utama:**

| Fungsi | Dipakai oleh | Perbedaan |
|---|---|---|
| `query_rag` | `POST /query` | tanya sekali putus, tanpa memori |
| `query_rag_conversational` | `POST /chat` | pakai riwayat percakapan |
| `prepare_conversational_stream` | `POST /chat/stream` | sama, tapi jawaban dikirim bertahap |

**`condense_question`** — pertanyaan lanjutan seperti "kalau 2024?" tidak bisa dicari apa adanya
(tidak ada kata "laba"). Fungsi ini meminta LLM menulis ulang menjadi pertanyaan mandiri
("Berapa laba bersih tahun 2024?") sebelum dicari ke database. Tanpa riwayat, langkah ini dilewati.

**`_retrieve_or_raise`** — mengambil chunk; bila kosong, melempar `RetrievalEmptyError`
dengan pesan yang membantu (router mengubahnya jadi HTTP 404).

### 4.7 `app/services/chat_history.py` — memori percakapan

Menyimpan riwayat per `session_id` di dictionary Python:

```python
_store = defaultdict(lambda: deque(maxlen=get_settings().max_history_turns * 2))
```
- `deque(maxlen=10)` = antrean yang otomatis membuang yang paling lama jika penuh → hanya 5 giliran
  terakhir diingat (tiap giliran = 1 pertanyaan + 1 jawaban = 2 pesan).
- `threading.Lock()` mencegah dua request bersamaan merusak data.
- ⚠️ Disimpan di RAM: hilang saat server restart dan tidak dibagi antar-server. Untuk production,
  ganti dengan Redis (cukup ubah file ini saja).

### 4.8 `app/models/schemas.py` — bentuk data

Class `BaseModel` dari Pydantic mendeskripsikan bentuk request/response:

```python
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
```
FastAPI otomatis memvalidasi: pertanyaan kosong atau >2000 karakter ditolak dengan HTTP 422 sebelum
kode Anda dijalankan. `response_model=...` di endpoint memastikan keluaran juga sesuai bentuk ini,
sekaligus menghasilkan dokumentasi otomatis di `/docs`.

### 4.9 `app/core/security.py` — API key

```python
async def verify_api_key(x_api_key: str | None = Header(default=None)):
    if not settings.api_key: return          # API_KEY kosong → auth mati (mode development)
    if x_api_key != settings.api_key: raise HTTPException(401, ...)
```
FastAPI otomatis memetakan parameter `x_api_key` ke header HTTP `X-API-Key`. Fungsi ini dipasang
sebagai *dependency* pada router sehingga berlaku untuk semua endpoint `/api/v1/*`.

### 4.10 `app/routers/rag.py` — daftar endpoint

| Endpoint | Fungsi |
|---|---|
| `POST /upload` | validasi file (harus PDF, ≤ batas MB, tidak kosong) → simpan sementara → `ingest_pdf` → hapus file sementara (`finally`) |
| `POST /query` | tanya sekali putus |
| `POST /chat` | tanya dengan memori |
| `POST /chat/stream` | sama, jawaban bertahap (SSE) |
| `GET /collections`, `GET /collections/{nama}/documents` | melihat isi database |
| `DELETE /collections/{nama}[/documents/{file}]` | menghapus |
| `DELETE /chat/{session_id}` | menghapus riwayat |

Hal-hal penting di file ini:

- `@limiter.limit("20/minute")` — batas request per IP.
- `try/except` bertingkat: `RetrievalEmptyError` → 404; error lain lewat `_friendly_error()` yang
  menerjemahkan error teknis (rate limit Groq, API key salah, koneksi putus) menjadi pesan yang
  mudah dipahami — pesan inilah yang muncul di notifikasi merah halaman demo.
- **Streaming:**
  ```python
  async def event_stream():
      async for token in token_gen:
          yield f"data: {json.dumps({'token': token})}\n\n"
  return StreamingResponse(event_stream(), media_type="text/event-stream")
  ```
  `yield` mengirim satu potongan lalu lanjut; format `data: ...\n\n` adalah standar *Server-Sent Events*.

### 4.11 `app/main.py` — merakit aplikasi

Urutan di file ini: buat `app = FastAPI(...)` → pasang rate limiter → pasang CORS → pasang middleware
logging → daftarkan router → sajikan halaman statis.

- **Middleware** `request_id_and_logging_middleware` berjalan pada SETIAP request: membuat ID unik
  (`X-Request-ID`), mengukur durasi, mencatat ke log, dan mengisi data metrics. ID yang sama muncul
  di respons dan log sehingga satu request mudah dilacak.
- `@app.exception_handler(Exception)` menangkap error yang tak terduga agar user mendapat pesan
  rapi, bukan stack trace.
- `_serve_page()` mengirim file HTML untuk `/`, `/demo/`, `/dashboard/`.

### 4.12 `app/services/metrics.py` — statistik

Penghitung sederhana di memori (jumlah upload/query/chat/error + 500 durasi terakhir) yang dibaca
dashboard lewat `GET /api/v1/metrics`. Cocok untuk demo; untuk production pakai Prometheus.

### 4.13 `static/demo.html` — halaman chat (JavaScript)

Bagian yang paling layak dipelajari:

1. **`fetch()`** — cara browser memanggil API. Upload memakai `FormData`, chat memakai JSON.
2. **Membaca streaming:**
   ```js
   const reader = res.body.getReader();
   while (true) {
     const { done, value } = await reader.read();   // ambil potongan berikutnya
     if (done) break;
     buffer += decoder.decode(value, { stream: true });
     const lines = buffer.split('\n\n');            // pisahkan per event SSE
     buffer = lines.pop();                          // sisa yang belum lengkap disimpan
     ...
   }
   ```
   `buffer` penting karena satu event bisa terpotong di tengah antara dua bacaan.
3. **`showToast(type, title, message)`** — membuat notifikasi sukses/error/info. Memakai
   `textContent` (bukan `innerHTML`) untuk teks dari server agar aman dari injeksi HTML.
4. **`errorText(err)`** — `fetch` yang gagal total (server mati) melempar `TypeError`; fungsi ini
   mengubahnya jadi pesan "Tidak bisa terhubung ke server…".
5. **`errorFrom(res, data, fallback)`** — server bisa membalas error dalam beberapa bentuk: `detail` berupa
   teks (error biasa), `detail` berupa *list* (validasi 422, kalau ditampilkan mentah jadi `[object Object]`),
   `{"error": ...}` (rate limit 429), atau tanpa isi. Fungsi ini menyeragamkan semuanya jadi satu kalimat Indonesia.
6. **`escapeHtml(s)`** — nama file dari user bisa berisi `<script>`. Setiap teks yang disisipkan lewat
   `innerHTML` harus di-escape agar tidak dieksekusi (serangan XSS).
7. **Tes browser (E2E)** — halaman ini diuji dengan Playwright: robot membuka Chromium, meng-upload PDF,
   bertanya, lalu memastikan toast sukses/error benar-benar muncul.

### 4.14 `tests/` — tes otomatis

Tes memverifikasi kode tanpa perlu menjalankan server sungguhan:

- `TestClient(app)` memanggil endpoint seolah-olah dari luar.
- `unittest.mock.patch(...)` mengganti fungsi mahal (LLM, database) dengan palsu, sehingga tes cepat,
  gratis, dan tidak butuh internet.
- Jalankan dengan `pytest -v`. Setiap kali mengubah kode, jalankan lagi untuk memastikan tidak ada
  yang rusak (inilah gunanya CI di GitHub Actions: tes otomatis jalan tiap push).

### 4.15 Docker & CI

- `Dockerfile` — resep membuat "kotak" berisi aplikasi + semua library, sehingga jalan sama di mana saja.
  Urutan `COPY requirements.txt` → `pip install` → `COPY app` disengaja: Docker menyimpan cache per
  langkah, jadi library tidak diinstall ulang kalau hanya kode yang berubah. Baris `CMD` sengaja
  menjalankan **1 worker saja** (alasannya di bagian 6, nomor 8).
- `docker-compose.yml` — menjalankan container, membaca `.env`, dan memasang *volume* agar database
  tidak hilang saat container dihapus.
- `.github/workflows/ci.yml` — menjalankan `pytest` otomatis di GitHub untuk setiap push.

---

## 5. Menelusuri Satu Pertanyaan dari Awal sampai Akhir

User mengetik **"Berapa laba bersih 2025?"** di halaman demo:

1. `demo.html` memanggil `POST /api/v1/chat/stream` berisi `session_id`, `question`, `collection`.
2. **Middleware** (`main.py`) memberi `X-Request-ID` dan mulai menghitung waktu.
3. **Dependency** `verify_api_key` mengecek API key (kalau diaktifkan).
4. **Validasi** `ChatRequest` memeriksa panjang pertanyaan.
5. Router mengambil riwayat: `get_history_messages(session_id)`.
6. `prepare_conversational_stream` → `condense_question` (riwayat kosong → pertanyaan dipakai apa adanya).
7. `retrieve_documents`: pertanyaan → `"query: Berapa laba bersih 2025?"` → vektor → Chroma mengembalikan
   6 chunk terdekat, masing-masing dengan skor.
8. `_format_docs` menyusun konteks: `[Sumber 1 | file: laporan.pdf | hal. 2] ...teks chunk...`
9. Prompt dikirim ke Groq. Token jawaban dikirim balik satu per satu lewat SSE.
10. Browser menyambung token menjadi kalimat; di akhir menerima `{"done": true, "sources": [...]}`
    lalu menampilkan kartu sitasi (nama file, halaman, skor).
11. `append_turn` menyimpan pasangan tanya-jawab ke memori; `metrics.increment("chats")`.

---

## 6. Jawaban Salah / Tidak Sesuai PDF? Cara Mendiagnosis

Periksa urut dari atas — jangan langsung menyalahkan LLM.

| # | Pemeriksaan | Gejala | Perbaikan |
|---|---|---|---|
| 1 | **Apakah PDF berisi teks asli?** Coba seleksi/copy teks di PDF. | Tidak bisa diseleksi = hasil scan. | Gunakan PDF bertext, atau tambahkan OCR. |
| 2 | **Model embedding multilingual?** Cek `EMBEDDING_MODEL` di `.env`. | Dokumen Indonesia + model `all-MiniLM` → chunk salah. | Set `intfloat/multilingual-e5-small`, upload ulang PDF. |
| 3 | **Lihat kartu sitasi** (nama file, halaman, skor %). | Halaman/skor tidak relevan → retrieval yang salah. | Naikkan `RETRIEVAL_K`, perbesar `CHUNK_SIZE`, perjelas pertanyaan. |
| 4 | **Collection tercampur?** | Jawaban berasal dari file lain. | Pakai `source_filter` atau collection terpisah per topik. |
| 5 | **Pertanyaan terlalu singkat** ("laba"). | Banyak chunk mengandung kata itu. | Tulis lengkap: "Berapa laba bersih tahun 2025?" |
| 6 | **Chunk terlalu kecil** — tabel terpotong dari header tahunnya. | Angka tertukar antar tahun. | `CHUNK_SIZE=1200` atau lebih; naikkan `CHUNK_OVERLAP`. |
| 7 | **Prompt kurang tegas.** | LLM menambah info dari luar dokumen. | Perketat `SYSTEM_PROMPT` di `rag_chain.py`. |
| 8 | **Server berjalan dengan lebih dari 1 worker?** Cek perintah `uvicorn` / `Dockerfile` — adakah `--workers 2`? | Kadang jawaban benar, kadang "tidak ada dokumen" / jawaban tidak menemukan file yang baru diupload — tergantung worker mana yang melayani. | Jalankan **1 proses saja**. Lihat penjelasan di bawah tabel. |

| 9 | **Dokumen masuk ke collection yang benar?** Buka `GET /api/v1/collections` setelah upload. | Upload dengan `collection=proyek-x` tapi semua file muncul di `default`, sehingga pertanyaan ke `proyek-x` kosong/salah file. | Di endpoint upload, parameter form harus `collection: str = Form("default")`. Lihat penjelasan di bawah. |

**Kenapa nomor 9 bisa terjadi?** FastAPI menebak asal tiap parameter dari tipenya. Parameter biasa (`collection: str`)
dianggap **query string** (`/upload?collection=x`). Padahal `curl -F "collection=x"` dan `FormData.append("collection", "x")`
mengirimnya di **body form**. Akibatnya nilai dari form diabaikan tanpa error, dan semua dokumen diam-diam masuk ke
`default`. `Form(...)` memberi tahu FastAPI: "baca dari body form". Ada tes regresi
(`test_upload_uses_collection_from_form_field`) yang akan gagal kalau bug ini muncul lagi.

**Kenapa nomor 8 bisa terjadi?** "Worker" adalah salinan program yang berjalan sendiri-sendiri. Tiap salinan
punya memorinya sendiri. ChromaDB versi *embedded* (yang kita pakai) menyimpan **indeks pencarian di memori**
proses yang membukanya. Saat worker A menerima upload, data masuk ke disk dan indeks milik A — tetapi indeks
milik worker B yang sudah terlanjur terbuka *tidak ikut diperbarui*. Kami membuktikannya dengan tes dua proses:
proses B menghitung `count() = 1` dan `get()` melihat dokumennya, tetapi `query()` (pencarian vektor) tetap
mengembalikan **kosong**; baru setelah koneksi dibuka ulang hasilnya muncul. Hal yang sama berlaku untuk riwayat
chat dan statistik dashboard (keduanya variabel di memori). Solusi jangka panjang: pakai database vektor
berbentuk *server* (Chroma server / Qdrant) dan Redis, baru boleh menambah worker.

**Eksperimen cepat:** tanya hal yang pasti ada di PDF lalu lihat kartu sitasinya. Kalau halaman sitasi
benar tetapi jawaban salah → masalah generation (prompt/LLM). Kalau halaman sitasi salah →
masalah retrieval (tabel di atas, nomor 2-6).

---

## 7. Latihan Mandiri (urut dari mudah)

1. **Ubah `RETRIEVAL_K`** menjadi 2, lalu 10. Amati kartu sitasi dan kualitas jawaban. Apa trade-off-nya?
2. **Ubah `CHUNK_SIZE`** menjadi 300 lalu 3000 (hapus collection & upload ulang tiap kali). Bandingkan jawaban
   untuk pertanyaan yang butuh tabel.
3. **Ubah `SYSTEM_PROMPT`**: minta jawaban dalam format poin-poin. Lihat efeknya.
4. **Tambah `print()`** di `retrieve_documents` untuk mencetak skor dan potongan teks tiap chunk.
   Ini cara terbaik "melihat" apa yang dilihat LLM.
5. **Tambah endpoint** `GET /api/v1/health/db` yang mengembalikan jumlah chunk di sebuah collection
   (petunjuk: `store._collection.count()`), lalu tulis tesnya.
6. **Tambah tes** baru di `tests/` untuk `_friendly_error` (beri error berisi "429", pastikan status 429).
7. **Tantangan:** ganti `chat_history.py` agar menyimpan ke file JSON sehingga memori bertahan saat server restart.

---

## 8. Jalur Belajar Lanjutan

1. **Python dasar** → fungsi, class, `try/except`, list/dict comprehension, `async/await`.
2. **FastAPI** → dokumentasi resmi (tutorial "First Steps" sampai "Dependencies").
3. **Konsep RAG** → pelajari *chunking strategy*, *hybrid search* (vektor + kata kunci), *reranking*.
4. **Evaluasi RAG** → buat 20 pasang tanya-jawab dari PDF Anda, ukur berapa yang dijawab benar setiap
   kali mengubah pengaturan. Ini yang membedakan "jalan" dari "bagus".
5. **Deploy** → Docker, lalu Railway/Render (lihat `GITHUB_UPLOAD.md`).
