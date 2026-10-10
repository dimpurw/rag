def test_upload_rejects_non_pdf(client, tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("ini bukan pdf")

    with open(file_path, "rb") as f:
        response = client.post(
            "/api/v1/upload",
            files={"file": ("test.txt", f, "text/plain")},
            data={"collection": "test"},
        )

    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_upload_rejects_empty_file(client, tmp_path):
    file_path = tmp_path / "empty.pdf"
    file_path.write_bytes(b"")

    with open(file_path, "rb") as f:
        response = client.post(
            "/api/v1/upload",
            files={"file": ("empty.pdf", f, "application/pdf")},
            data={"collection": "test"},
        )

    assert response.status_code == 400


def test_query_rejects_empty_question(client):
    response = client.post(
        "/api/v1/query",
        json={"question": "", "collection": "test"},
    )
    assert response.status_code == 422


def test_query_rejects_missing_collection(client):
    response = client.post(
        "/api/v1/query",
        json={"question": "Apa isi dokumen ini?"},
    )
    assert response.status_code == 422


def test_chat_requires_session_id(client):
    response = client.post(
        "/api/v1/chat",
        json={"question": "Halo", "collection": "test"},
    )
    assert response.status_code == 422


def test_chat_rejects_too_long_question(client):
    response = client.post(
        "/api/v1/chat",
        json={
            "session_id": "s1",
            "question": "a" * 3000,
            "collection": "test",
        },
    )
    assert response.status_code == 422
