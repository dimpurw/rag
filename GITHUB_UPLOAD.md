# Tutorial: Upload Proyek Ini ke GitHub

Panduan dari nol — cocok walau Anda belum pernah pakai Git/GitHub sama sekali.

---

## Langkah 0 — Persiapan

### Cek apakah Git sudah terinstall
```bash
git --version
```
Kalau belum ada, install dulu:
- **Windows**: download di https://git-scm.com/download/win
- **Mac**: `brew install git` (atau install Xcode Command Line Tools)
- **Linux**: `sudo apt install git` (Ubuntu/Debian) atau `sudo dnf install git` (Fedora)

### Buat akun GitHub (kalau belum punya)
Daftar gratis di https://github.com/signup

### Setup identitas Git (sekali saja, per komputer)
```bash
git config --global user.name "Nama Anda"
git config --global user.email "email@anda.com"
```
Gunakan email yang sama dengan akun GitHub Anda.

---

## Langkah 1 — Buat Repository Baru di GitHub

1. Login ke https://github.com
2. Klik tombol **+** di pojok kanan atas → **New repository**
3. Isi form:
   - **Repository name**: misal `pustaka-rag-api` (bebas, tapi pilih nama yang deskriptif untuk portofolio)
   - **Description**: misal "RAG API production-ready dengan LangChain, Groq, dan ChromaDB — upload PDF, tanya jawab dengan sumber kutipan"
   - **Visibility**: pilih **Public** (supaya bisa ditunjukkan ke recruiter/di portofolio)
   - **JANGAN** centang "Add a README file", "Add .gitignore", atau "Choose a license" — karena project ini sudah punya semuanya. Biarkan repo kosong.
4. Klik **Create repository**
5. GitHub akan menampilkan halaman berisi URL repo, formatnya seperti:
   ```
   https://github.com/username-anda/pustaka-rag-api.git
   ```
   Salin URL ini, akan dipakai di Langkah 3.

---

## Langkah 2 — Siapkan Folder Project Secara Lokal

Extract `rag-backend.zip` kalau belum, lalu masuk ke foldernya:
```bash
cd rag-backend
```

Pastikan `.env` **tidak ada** di folder ini (kalau ada, hapus dulu — file ini berisi API key rahasia dan sudah otomatis diabaikan oleh `.gitignore`, tapi baiknya dicek manual):
```bash
rm -f .env
```

---

## Langkah 3 — Inisialisasi Git & Push Pertama Kali

Jalankan urutan perintah ini persis di dalam folder `rag-backend`:

```bash
# 1. Inisialisasi git di folder ini
git init

# 2. Tambahkan semua file (yang di .gitignore otomatis dilewati)
git add .

# 3. Buat commit pertama
git commit -m "Initial commit: RAG API dengan LangChain, Groq, dan ChromaDB"

# 4. Ganti nama branch utama jadi 'main' (standar GitHub saat ini)
git branch -M main

# 5. Hubungkan ke repo GitHub yang tadi dibuat (GANTI URL dengan punya Anda)
git remote add origin https://github.com/username-anda/pustaka-rag-api.git

# 6. Push ke GitHub
git push -u origin main
```

Kalau diminta login, GitHub sekarang mewajibkan **Personal Access Token** (bukan password biasa) — lihat Langkah 4 kalau belum punya.

---

## Langkah 4 — Autentikasi (Kalau Diminta Login)

GitHub tidak lagi menerima password biasa untuk `git push` lewat command line. Ada dua opsi:

### Opsi A — Personal Access Token (paling umum)
1. Buka https://github.com/settings/tokens
2. Klik **Generate new token** → **Generate new token (classic)**
3. Beri nama (misal "laptop-saya"), centang scope **repo**
4. Klik **Generate token**, salin token yang muncul (hanya tampil sekali!)
5. Saat `git push` minta password, **paste token ini** (bukan password akun GitHub Anda)

### Opsi B — GitHub CLI (lebih mudah kalau sering dipakai)
```bash
# Install: https://cli.github.com
gh auth login
```
Ikuti instruksi di layar (pilih HTTPS, login via browser). Setelah ini, `git push` tidak akan minta autentikasi lagi.

---

## Langkah 5 — Verifikasi Upload Berhasil

1. Refresh halaman repo Anda di GitHub — semua file harus sudah muncul
2. Klik tab **Actions** — harusnya ada workflow **CI** yang otomatis jalan (karena project ini sudah include `.github/workflows/ci.yml`). Tunggu beberapa menit, pastikan hasilnya ✅ hijau, bukan ❌ merah.
3. Kalau CI merah, klik untuk lihat log error — biasanya karena `requirements.txt` atau versi Python, cek pesan errornya.

---

## Langkah 6 — Update Repo di Kemudian Hari

Setelah ada perubahan kode:
```bash
git add .
git commit -m "Deskripsikan perubahan Anda di sini"
git push
```

---

## Langkah 7 — Mempercantik Repo untuk Portofolio

### Tambahkan topics (tag pencarian)
Di halaman repo GitHub, klik ⚙️ di sebelah "About" → tambahkan topics seperti:
`rag` `langchain` `fastapi` `llm` `groq` `chromadb` `python` `ai`

### Isi kolom "About"
Klik ⚙️ di sebelah "About" → isi:
- **Description**: ringkasan 1 kalimat
- **Website**: kalau sudah deploy (lihat Langkah 8), taruh link live demo-nya di sini

### Tambahkan screenshot/GIF ke README
1. Jalankan server lokal, buka `/demo/` atau `/` (landing page)
2. Screenshot atau rekam layar singkat (tool gratis: [ShareX](https://getsharex.com/) untuk Windows, `Cmd+Shift+5` untuk Mac, atau [Peek](https://github.com/phw/peek) untuk Linux — bisa langsung jadi GIF)
3. Upload gambar ke repo (bisa lewat drag-and-drop langsung ke kolom edit README di GitHub, nanti otomatis dapat URL)
4. Tempel di paling atas `README.md`:
   ```markdown
   ![Demo Pustaka](URL_gambar_dari_github)
   ```

### Pin ke profil GitHub Anda
Di halaman profil GitHub Anda → klik **Customize your pins** → pilih repo ini supaya muncul di halaman utama profil.

---

## Langkah 8 (Bonus) — Deploy Supaya Bisa Dicoba Live

Repo yang bisa "dicoba langsung" (bukan cuma dibaca kodenya) jauh lebih meyakinkan untuk portofolio. Dua opsi gratis yang mendukung Docker:

### Railway (paling mudah)
1. Daftar di https://railway.app (bisa pakai akun GitHub)
2. **New Project** → **Deploy from GitHub repo** → pilih repo Anda
3. Railway otomatis mendeteksi `Dockerfile`
4. Di tab **Variables**, tambahkan environment variable `GROQ_API_KEY` (dan `API_KEY` kalau mau proteksi)
5. Setelah deploy selesai, Railway kasih URL publik — itu link live demo Anda

### Render
1. Daftar di https://render.com
2. **New** → **Web Service** → hubungkan ke repo GitHub Anda
3. Pilih **Docker** sebagai environment
4. Tambahkan environment variable yang sama seperti di atas
5. Deploy, dapat URL publik

> Catatan: karena embedding model (HuggingFace) butuh RAM sekitar 500MB-1GB, pastikan pilih tier yang cukup (biasanya masih masuk free tier tapi bisa agak lambat di cold start pertama).

---

## Troubleshooting Umum

| Error | Penyebab | Solusi |
|---|---|---|
| `fatal: not a git repository` | Belum `git init` | Jalankan `git init` dulu di folder project |
| `remote origin already exists` | Sudah pernah `git remote add` sebelumnya | `git remote set-url origin <URL>` untuk ganti, atau `git remote remove origin` lalu ulangi |
| `Support for password authentication was removed` | Pakai password biasa, bukan token | Lihat Langkah 4, pakai Personal Access Token |
| `Updates were rejected because the remote contains work...` | Repo GitHub tidak benar-benar kosong (ada README auto-generated) | `git pull origin main --allow-unrelated-histories` lalu push lagi |
| File `.env` ikut ter-upload | `.gitignore` tidak terbaca / file sudah ter-track sebelum ditambahkan ke `.gitignore` | `git rm --cached .env` lalu commit ulang. **Segera ganti API key Anda** kalau sudah terlanjur ter-push ke repo public |
