def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


def test_root_serves_landing_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Pustaka" in response.text


def test_demo_page_served(client):
    response = client.get("/demo/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_dashboard_page_served(client):
    response = client.get("/dashboard/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_metrics_endpoint(client):
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    body = response.json()
    assert "total_uploads" in body
    assert "avg_response_time_ms" in body


def test_openapi_schema_generated(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/upload" in paths
    assert "/api/v1/query" in paths
    assert "/api/v1/chat" in paths
    assert "/api/v1/chat/stream" in paths
