"""Rendered page-count endpoint tests."""

from pathlib import Path

import fitz
from fastapi.testclient import TestClient

import app as pyconvert_app


def test_pdf_info_returns_exact_page_count(tmp_path: Path):
    pdf_path = tmp_path / "three-pages.pdf"
    document = fitz.open()
    for _ in range(3):
        document.new_page()
    document.save(pdf_path)
    document.close()

    with TestClient(pyconvert_app.app) as client:
        response = client.post(
            "/pymupdf/pdf-info",
            files={"file": (pdf_path.name, pdf_path.read_bytes(), "application/pdf")},
        )

    assert response.status_code == 200
    assert response.json() == {"page_count": 3}


def test_pdf_info_rejects_invalid_pdf():
    with TestClient(pyconvert_app.app) as client:
        response = client.post(
            "/pymupdf/pdf-info",
            files={"file": ("broken.pdf", b"not a PDF", "application/pdf")},
        )

    assert response.status_code == 400
