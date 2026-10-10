"""
Tes alur ingestion -> retrieval memakai ChromaDB SUNGGUHAN (di folder sementara),
tetapi dengan embedding palsu supaya tidak perlu mengunduh model dan tetap cepat.

Embedding palsu (DeterministicFakeEmbedding) menghasilkan vektor yang selalu sama untuk teks yang
sama. Artinya: bertanya dengan teks persis sebuah chunk akan menemukan chunk itu di urutan pertama.
Cukup untuk menguji LOGIKA kode kita (filter, halaman, baris rusak, dll).
"""
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding

from app.services import ingestion, vector_store


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Siapkan pengaturan palsu + folder sementara + embedding palsu untuk modul-modul terkait."""
    fake_settings = SimpleNamespace(
        chroma_dir=str(tmp_path / "chroma"),
        upload_dir=str(tmp_path / "uploads"),
        embedding_model="test/fake-model",
        chunk_size=1200,
        chunk_overlap=200,
    )
    fake_embeddings = DeterministicFakeEmbedding(size=16)
    monkeypatch.setattr(vector_store, "get_settings", lambda: fake_settings)
    monkeypatch.setattr(ingestion, "get_settings", lambda: fake_settings)
    monkeypatch.setattr(vector_store, "get_embeddings", lambda: fake_embeddings)
    return SimpleNamespace(settings=fake_settings, embeddings=fake_embeddings, tmp=tmp_path)


def _fake_pdf_loader(pages):
    """Buat pengganti PyPDFLoader yang mengembalikan halaman-halaman palsu."""
    class FakeLoader:
        def __init__(self, path):
            self.path = path

        def load(self):
            return [Document(page_content=text, metadata={"page": i}) for i, text in enumerate(pages)]
    return FakeLoader


def test_ingest_page_numbers_start_at_one_and_empty_pages_dropped(env, monkeypatch):
    # Halaman ke-2 (indeks 1) kosong, seperti halaman scan tanpa teks.
    monkeypatch.setattr(ingestion, "PyPDFLoader", _fake_pdf_loader(["Laba bersih 412 miliar", "   ", "Total aset 3055 miliar"]))

    result = ingestion.ingest_pdf("dummy.pdf", "keuangan", "laporan.pdf")

    assert result["num_pages"] == 3
    assert result["num_chunks"] == 2  # chunk kosong dibuang

    docs = vector_store.retrieve_documents("keuangan", "Laba bersih 412 miliar", k=5)
    pages = sorted(d.metadata["page"] for d in docs)
    # PyPDF memberi halaman 0 dan 2 -> kita simpan sebagai 1 dan 3 (sesuai nomor di PDF).
    assert pages == [1, 3]


def test_ingest_raises_when_pdf_has_no_text(env, monkeypatch):
    monkeypatch.setattr(ingestion, "PyPDFLoader", _fake_pdf_loader(["", "  "]))
    with pytest.raises(ingestion.IngestionError):
        ingestion.ingest_pdf("dummy.pdf", "kosong", "scan.pdf")


def test_retrieval_finds_exact_text_first_and_returns_score(env, monkeypatch):
    monkeypatch.setattr(ingestion, "PyPDFLoader", _fake_pdf_loader(["Kebijakan cuti tahunan 12 hari", "Prosedur lembur dan upah"]))
    ingestion.ingest_pdf("dummy.pdf", "hr", "hr.pdf")

    docs = vector_store.retrieve_documents("hr", "Kebijakan cuti tahunan 12 hari", k=2)

    assert docs[0].page_content == "Kebijakan cuti tahunan 12 hari"
    assert docs[0].metadata["score"] > 0.99          # teks identik -> kemiripan ~1
    assert 0.0 <= docs[1].metadata["score"] <= 1.0


def test_retrieval_skips_corrupted_rows_instead_of_crashing(env, monkeypatch):
    """Reproduksi error 'page_content ... NoneType': baris di Chroma tanpa teks dokumen."""
    monkeypatch.setattr(ingestion, "PyPDFLoader", _fake_pdf_loader(["Isi dokumen yang valid"]))
    ingestion.ingest_pdf("dummy.pdf", "campur", "bagus.pdf")

    # Suntik baris rusak: ada vektor & metadata, tetapi kolom dokumen kosong (None).
    store = vector_store.get_vector_store("campur")
    bad_vector = env.embeddings.embed_query("Isi dokumen yang valid")  # sengaja sama -> pasti ikut terambil
    store._collection.add(ids=["rusak-1"], embeddings=[bad_vector], metadatas=[{"source": "rusak.pdf", "page": 1}])

    docs = vector_store.retrieve_documents("campur", "Isi dokumen yang valid", k=5)

    assert len(docs) == 1
    assert docs[0].metadata["source"] == "bagus.pdf"


def test_source_filter_limits_search_to_chosen_files(env, monkeypatch):
    monkeypatch.setattr(ingestion, "PyPDFLoader", _fake_pdf_loader(["Teks dari file A"]))
    ingestion.ingest_pdf("dummy.pdf", "multi", "a.pdf")
    monkeypatch.setattr(ingestion, "PyPDFLoader", _fake_pdf_loader(["Teks dari file B"]))
    ingestion.ingest_pdf("dummy.pdf", "multi", "b.pdf")

    only_b = vector_store.retrieve_documents("multi", "Teks", k=5, source_filter=["b.pdf"])
    both = vector_store.retrieve_documents("multi", "Teks", k=5, source_filter=["a.pdf", "b.pdf"])

    assert {d.metadata["source"] for d in only_b} == {"b.pdf"}
    assert {d.metadata["source"] for d in both} == {"a.pdf", "b.pdf"}


def test_list_collections_has_no_phantom_langchain_collection(env, monkeypatch):
    monkeypatch.setattr(ingestion, "PyPDFLoader", _fake_pdf_loader(["Isi"]))
    ingestion.ingest_pdf("dummy.pdf", "koleksi-satu", "x.pdf")

    assert vector_store.list_collections() == ["koleksi-satu"]


def test_list_and_delete_single_document(env, monkeypatch):
    monkeypatch.setattr(ingestion, "PyPDFLoader", _fake_pdf_loader(["Dokumen satu"]))
    ingestion.ingest_pdf("dummy.pdf", "hapus", "satu.pdf")
    monkeypatch.setattr(ingestion, "PyPDFLoader", _fake_pdf_loader(["Dokumen dua"]))
    ingestion.ingest_pdf("dummy.pdf", "hapus", "dua.pdf")

    assert vector_store.list_documents_in_collection("hapus") == ["dua.pdf", "satu.pdf"]
    assert vector_store.delete_document_from_collection("hapus", "satu.pdf") == 1
    assert vector_store.list_documents_in_collection("hapus") == ["dua.pdf"]
    assert vector_store.delete_document_from_collection("hapus", "tidak-ada.pdf") == 0


def test_database_folder_is_separated_per_embedding_model(env, monkeypatch):
    monkeypatch.setattr(ingestion, "PyPDFLoader", _fake_pdf_loader(["Isi model lama"]))
    ingestion.ingest_pdf("dummy.pdf", "uji", "lama.pdf")
    assert vector_store.list_collections() == ["uji"]

    # Ganti model embedding -> harus memakai folder database baru yang kosong.
    env.settings.embedding_model = "test/model-baru"
    assert vector_store.list_collections() == []


def test_empty_collection_returns_no_documents(env):
    assert vector_store.retrieve_documents("belum-ada", "apa saja", k=3) == []
