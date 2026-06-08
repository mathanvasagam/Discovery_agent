import pytest
from backend.core.ingestor import ingest_document, _sliding_chunks, _detect_content_type

def test_sliding_chunks():
    text = "This is a test of the sliding chunks logic. It should break into multiple chunks."
    chunks = _sliding_chunks(text, chunk_size=20, chunk_overlap=5)
    # The string is 78 characters long.
    # Chunk 1: 0-20
    # Chunk 2: 15-35
    # ...
    assert len(chunks) > 1
    assert chunks[0][0].startswith("This is a test")

def test_detect_content_type():
    assert _detect_content_type("test.txt", None) == "text/plain"
    assert _detect_content_type("test.pdf", None) == "application/pdf"
    assert _detect_content_type("test.csv", None) == "text/csv"
    assert _detect_content_type("test.jpg", None) == "image/jpg"

def test_ingest_file_not_found():
    chunks = ingest_document("nonexistent_file.txt")
    assert chunks == []

def test_ingest_empty_file(tmp_path):
    p = tmp_path / "empty.txt"
    p.write_text("")
    chunks = ingest_document(str(p))
    assert chunks == []

def test_ingest_text_file(tmp_path):
    p = tmp_path / "test.txt"
    p.write_text("Hello\nWorld")
    chunks = ingest_document(str(p))
    assert len(chunks) == 2
    assert chunks[0]["content"] == "Hello"
    assert chunks[1]["content"] == "World"

def test_ingest_excel_file(tmp_path):
    import openpyxl
    p = tmp_path / "test.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Systems"
    ws.append(["Name", "Category", "Auth"])
    ws.append(["Salesforce", "CRM", "OAuth2"])
    ws.append(["Stripe", "Payment", "API Key"])
    wb.save(p)

    chunks = ingest_document(str(p))
    assert len(chunks) == 3
    assert "Salesforce" in chunks[1]["content"]
    assert "Stripe" in chunks[2]["content"]
    assert chunks[1]["metadata"]["sheet_name"] == "Systems"

