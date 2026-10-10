"""Tes penerjemah error teknis -> pesan ramah yang tampil sebagai toast di halaman demo."""
from unittest.mock import patch

from app.routers.rag import _friendly_error


def test_rate_limit_error_is_translated():
    status, message = _friendly_error(Exception("Error code: 429 - rate_limit_exceeded"))
    assert status == 429
    assert "tunggu" in message.lower()


def test_invalid_api_key_is_translated():
    status, message = _friendly_error(Exception("Error code: 401 - invalid_api_key"))
    assert status == 502
    assert "GROQ_API_KEY" in message


def test_connection_error_is_translated():
    status, _ = _friendly_error(Exception("Connection error."))
    assert status == 503


def test_unknown_error_falls_back_to_500():
    status, message = _friendly_error(Exception("sesuatu yang aneh"))
    assert status == 500
    assert "sesuatu yang aneh" in message


def test_endpoint_returns_friendly_message_on_groq_rate_limit(client):
    with patch("app.routers.rag.query_rag", side_effect=Exception("429 rate limit")):
        response = client.post("/api/v1/query", json={"question": "Halo", "collection": "test"})
    assert response.status_code == 429
    assert "Groq" in response.json()["detail"]
