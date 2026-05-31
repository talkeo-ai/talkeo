from fastapi.testclient import TestClient

from app.main import app


def test_stream_hello_streams_sse():
    client = TestClient(app)
    with client.stream("GET", "/api/v1/stream/hello") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    assert "data: Hello" in body
    assert "event: done" in body
    assert "[DONE]" in body
