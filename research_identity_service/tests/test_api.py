import sys
from pathlib import Path

# Add research_identity_service to path
sys.path.append(str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.extractors.pdf_extractor import extract_text_from_pdf
from io import BytesIO

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "Research Identity Service"}

def test_pdf_extraction():
    dummy_stream = BytesIO(b"")
    text = extract_text_from_pdf(dummy_stream)
    assert isinstance(text, str)
