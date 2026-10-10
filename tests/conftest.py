import os

os.environ.setdefault("GROQ_API_KEY", "test-dummy-key")

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)
