from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_create_transcripcion():
    response = client.post("/transcripciones/", json={
        "fuente": "Radio Test",
        "timestamp_inicio": "2025-05-13T10:00:00",
        "timestamp_fin": "2025-05-13T10:00:15",
        "texto": "Esto es una prueba"
    })
    assert response.status_code == 200
    assert response.json()["ok"] is True
