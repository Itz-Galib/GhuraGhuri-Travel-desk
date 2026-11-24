from fastapi.testclient import TestClient

from app.core.errors import ConflictError
from app.main import create_app


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"]
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]


def test_request_id_is_echoed_when_valid(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "test-request-123"})

    assert response.headers["X-Request-ID"] == "test-request-123"


def test_invalid_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "bad id with spaces"})

    assert response.headers["X-Request-ID"] != "bad id with spaces"
    assert len(response.headers["X-Request-ID"]) == 32


def test_security_headers_are_present(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_validation_errors_map_to_400_envelope() -> None:
    app = create_app()

    @app.get("/test/validate")
    def validate(limit: int) -> dict[str, int]:
        return {"limit": limit}

    with TestClient(app) as test_client:
        response = test_client.get("/test/validate", params={"limit": "not-a-number"})

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["errors"][0]["loc"] == ["query", "limit"]
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_domain_errors_use_their_status_and_code() -> None:
    app = create_app()

    @app.get("/test/conflict")
    def conflict() -> None:
        raise ConflictError("Seats are no longer available", details={"seats_left": 0})

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/test/conflict")

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "CONFLICT"
    assert error["message"] == "Seats are no longer available"
    assert error["details"] == {"seats_left": 0}
