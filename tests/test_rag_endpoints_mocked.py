from unittest.mock import patch

from app.services.rag_chain import RetrievalEmptyError


def test_query_success_mocked(client):
    fake_result = {
        "answer": "Ini jawaban dummy dari mock.",
        "sources": [{"source": "contoh.pdf", "page": 1, "snippet": "cuplikan teks..."}],
    }
    with patch("app.routers.rag.query_rag", return_value=fake_result):
        response = client.post(
            "/api/v1/query",
            json={"question": "Apa isi dokumen ini?", "collection": "test"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Ini jawaban dummy dari mock."
    assert body["sources"][0]["source"] == "contoh.pdf"


def test_query_returns_404_when_no_relevant_docs(client):
    with patch("app.routers.rag.query_rag", side_effect=RetrievalEmptyError("Tidak ditemukan dokumen.")):
        response = client.post(
            "/api/v1/query",
            json={"question": "Pertanyaan acak", "collection": "kosong"},
        )

    assert response.status_code == 404


def test_chat_success_mocked_and_saves_history(client):
    fake_result = {
        "answer": "Jawaban percakapan dummy.",
        "sources": [],
        "standalone_question": "Apa isi dokumen ini?",
    }
    with patch("app.routers.rag.query_rag_conversational", return_value=fake_result) as mock_chat, \
         patch("app.routers.rag.append_turn") as mock_append:
        response = client.post(
            "/api/v1/chat",
            json={"session_id": "sess-1", "question": "Apa isi dokumen ini?", "collection": "test"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "sess-1"
    assert body["standalone_question"] == "Apa isi dokumen ini?"
    mock_chat.assert_called_once()
    mock_append.assert_called_once_with("sess-1", "Apa isi dokumen ini?", "Jawaban percakapan dummy.")


def test_clear_chat_history_endpoint(client):
    with patch("app.routers.rag.clear_session") as mock_clear:
        response = client.delete("/api/v1/chat/sess-1")

    assert response.status_code == 200
    mock_clear.assert_called_once_with("sess-1")


def test_delete_specific_document_success(client):
    with patch("app.routers.rag.delete_document_from_collection", return_value=3):
        response = client.delete("/api/v1/collections/test/documents/laporan.pdf")

    assert response.status_code == 200
    assert response.json()["chunks_deleted"] == 3


def test_delete_specific_document_not_found(client):
    with patch("app.routers.rag.delete_document_from_collection", return_value=0):
        response = client.delete("/api/v1/collections/test/documents/tidak-ada.pdf")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Regresi: nilai `collection` dari form upload HARUS sampai ke proses ingest.
# Bug lama: parameter `collection` dibaca sebagai query-string, sehingga semua upload
# (dari curl -F maupun halaman demo) diam-diam masuk ke collection "default".
# ---------------------------------------------------------------------------
def _upload(client, **form_data):
    """Kirim upload PDF palsu; ingest & penyimpanan file di-mock. Mengembalikan (response, mock_ingest)."""
    def fake_ingest(path, collection_name, source_filename):
        return {"filename": source_filename, "collection": collection_name, "num_chunks": 1, "num_pages": 1}

    with patch("app.routers.rag.save_upload_file", return_value="/tmp/tidak-ada.pdf"), \
         patch("app.routers.rag.ingest_pdf", side_effect=fake_ingest) as mock_ingest:
        response = client.post(
            "/api/v1/upload",
            files={"file": ("laporan.pdf", b"%PDF-1.4 isi palsu", "application/pdf")},
            data=form_data,
        )
    return response, mock_ingest


def test_upload_uses_collection_from_form_field(client):
    response, mock_ingest = _upload(client, collection="proyek-x")

    assert response.status_code == 200
    assert mock_ingest.call_args.kwargs["collection_name"] == "proyek-x"   # bukan "default"
    assert response.json()["collection"] == "proyek-x"


def test_upload_defaults_to_default_collection_when_not_given(client):
    response, mock_ingest = _upload(client)

    assert response.status_code == 200
    assert mock_ingest.call_args.kwargs["collection_name"] == "default"
