"""Unit tests for LibreOffice HTML to DOCX handling."""

from io import BytesIO
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from convert.config import ConversionService


WORDPROCESSINGML_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WORDPROCESSINGML_NS = {"w": WORDPROCESSINGML_NAMESPACE}


def _build_docx_with_paragraphs(paragraphs: list[str]) -> bytes:
    """Create a minimal DOCX payload with the provided paragraph texts."""
    body_xml = []
    for paragraph_text in paragraphs:
        if paragraph_text:
            body_xml.append(
                "<w:p><w:r><w:t>"
                f"{escape(paragraph_text)}"
                "</w:t></w:r></w:p>"
            )
        else:
            body_xml.append("<w:p><w:r/></w:p>")

    document_xml = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{WORDPROCESSINGML_NAMESPACE}">'
        f'<w:body>{"".join(body_xml)}</w:body>'
        f'</w:document>'
    )
    content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
</Types>
"""

    output = BytesIO()
    with ZipFile(output, "w") as docx_zip:
        docx_zip.writestr("[Content_Types].xml", content_types_xml)
        docx_zip.writestr("word/document.xml", document_xml)
    return output.getvalue()


def _get_docx_paragraphs(docx_content: bytes) -> list[str]:
    """Extract paragraph texts from a DOCX payload."""
    with ZipFile(BytesIO(docx_content)) as docx_zip:
        document_xml = docx_zip.read("word/document.xml")

    document_root = ET.fromstring(document_xml)
    paragraphs = []
    for paragraph in document_root.findall(".//w:body/w:p", WORDPROCESSINGML_NS):
        paragraph_text = "".join(
            (node.text or "")
            for node in paragraph.findall(".//w:t", WORDPROCESSINGML_NS)
        )
        paragraphs.append(paragraph_text)
    return paragraphs


def _build_namespaced_docx_with_leading_blank_paragraphs() -> bytes:
        """Create a DOCX payload that mimics Word's compatibility namespaces."""
        document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
                        xmlns:w="{WORDPROCESSINGML_NAMESPACE}"
                        xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
                        xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
                        mc:Ignorable="w14 wp14">
    <w:body>
        <w:p><w:r/></w:p>
        <w:p><w:r/></w:p>
        <w:p><w:r><w:t>Via Marie Mutiangpili</w:t></w:r></w:p>
        <w:sectPr><w:pgSz w:w="12240" w:h="15840" /></w:sectPr>
    </w:body>
</w:document>
'''
        content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="xml" ContentType="application/xml"/>
</Types>
"""

        output = BytesIO()
        with ZipFile(output, "w") as docx_zip:
                docx_zip.writestr("[Content_Types].xml", content_types_xml)
                docx_zip.writestr("word/document.xml", document_xml)
        return output.getvalue()


def _build_docx_with_table_and_empty_body_paragraphs() -> bytes:
    """Create a DOCX with empty body paragraphs plus a nested table paragraph."""
    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{WORDPROCESSINGML_NAMESPACE}">
    <w:body>
        <w:p><w:r><w:t>Heading</w:t></w:r></w:p>
        <w:p><w:r/></w:p>
        <w:tbl>
            <w:tr>
                <w:tc>
                    <w:p><w:r/></w:p>
                    <w:p><w:r><w:t>Cell text</w:t></w:r></w:p>
                </w:tc>
            </w:tr>
        </w:tbl>
        <w:p><w:r><w:t>After table</w:t></w:r></w:p>
        <w:sectPr><w:pgSz w:w="12240" w:h="15840" /></w:sectPr>
    </w:body>
</w:document>
'''
    content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="xml" ContentType="application/xml"/>
</Types>
"""

    output = BytesIO()
    with ZipFile(output, "w") as docx_zip:
        docx_zip.writestr("[Content_Types].xml", content_types_xml)
        docx_zip.writestr("word/document.xml", document_xml)
    return output.getvalue()


def _build_docx_with_rule_paragraph() -> bytes:
    """Create a DOCX with a border-only paragraph that mimics an HTML hr."""
    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{WORDPROCESSINGML_NAMESPACE}">
    <w:body>
        <w:p><w:r><w:t>Header</w:t></w:r></w:p>
        <w:p>
            <w:pPr>
                <w:pBdr>
                    <w:bottom w:val="single" w:sz="6" w:space="1" w:color="auto"/>
                </w:pBdr>
            </w:pPr>
            <w:r/>
        </w:p>
        <w:p><w:r><w:t>After header</w:t></w:r></w:p>
        <w:sectPr><w:pgSz w:w="12240" w:h="15840" /></w:sectPr>
    </w:body>
</w:document>
'''
    content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
</Types>
"""

    output = BytesIO()
    with ZipFile(output, "w") as docx_zip:
        docx_zip.writestr("[Content_Types].xml", content_types_xml)
        docx_zip.writestr("word/document.xml", document_xml)
    return output.getvalue()


class FakeResponse:
    """Minimal response object for mocked LibreOffice calls."""

    def __init__(self, content: bytes):
        self.status_code = 200
        self.content = content
        self.text = "ok"


class RecordingLibreOfficeClient:
    """Capture multipart fields sent to the LibreOffice backend."""

    def __init__(self, response_content: bytes):
        self.calls = []
        self.response_content = response_content

    async def post(self, url, files=None, data=None):
        self.calls.append({"url": url, "files": files, "data": data})
        return FakeResponse(self.response_content)


class RecordingPyconvertFactory:
    """Capture html4docx proxy calls and return a mocked DOCX payload."""

    def __init__(self, response_content: bytes):
        self.calls = []
        self.response_content = response_content

    async def post_with_retry(self, service_type, url, files=None, data=None):
        self.calls.append(
            {
                "service_type": service_type,
                "url": url,
                "files": files,
                "data": data,
            }
        )
        return FakeResponse(self.response_content)


def test_docx_cleanup_preserves_word_compatibility_namespaces():
    """Leading-paragraph cleanup must not strip mc:Ignorable namespace prefixes."""
    from convert.utils.conversion_core import _strip_leading_empty_docx_paragraphs

    cleaned_docx = _strip_leading_empty_docx_paragraphs(
        _build_namespaced_docx_with_leading_blank_paragraphs()
    )

    with ZipFile(BytesIO(cleaned_docx)) as docx_zip:
        document_xml = docx_zip.read("word/document.xml").decode("utf-8")

    assert 'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"' in document_xml
    assert 'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"' in document_xml
    assert 'xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"' in document_xml
    assert 'mc:Ignorable="w14 wp14"' in document_xml
    assert _get_docx_paragraphs(cleaned_docx) == ["Via Marie Mutiangpili"]


def test_docx_cleanup_strips_empty_body_paragraphs_beyond_document_top():
    """Cleanup should remove empty direct-body paragraphs throughout the document."""
    from convert.utils.conversion_core import _strip_leading_empty_docx_paragraphs

    cleaned_docx = _strip_leading_empty_docx_paragraphs(
        _build_docx_with_paragraphs(
            [
                "Via Marie Mutiangpili",
                "",
                "Professional Experience",
                "",
                "Medical Technologist",
                "",
                "Bataan, PH",
            ]
        )
    )

    assert _get_docx_paragraphs(cleaned_docx) == [
        "Via Marie Mutiangpili",
        "Professional Experience",
        "Medical Technologist",
        "Bataan, PH",
    ]


def test_docx_cleanup_keeps_nested_table_paragraphs():
    """Only direct body paragraphs should be stripped; nested table paragraphs stay."""
    from convert.utils.conversion_core import _strip_leading_empty_docx_paragraphs

    cleaned_docx = _strip_leading_empty_docx_paragraphs(
        _build_docx_with_table_and_empty_body_paragraphs()
    )

    with ZipFile(BytesIO(cleaned_docx)) as docx_zip:
        document_xml = docx_zip.read("word/document.xml").decode("utf-8")

    assert _get_docx_paragraphs(cleaned_docx) == ["Heading", "After table"]
    assert "<w:tbl>" in document_xml
    assert "<w:p><w:r/></w:p>" in document_xml
    assert "Cell text" in document_xml


def test_html_docx_default_html4docx_strips_leading_blank_paragraphs(client, monkeypatch):
    """Default html4docx output should not keep empty paragraphs at the top."""
    from convert.utils import http_client

    mocked_docx = _build_docx_with_paragraphs(
        [
            "",
            "",
            "Via Marie Mutiangpili",
            "vmarvmar23@gmail.com | +63 905 590 4276",
            "Bataan, PH",
            "Professional Summary",
        ]
    )
    recording_factory = RecordingPyconvertFactory(mocked_docx)

    monkeypatch.setattr(
        http_client,
        "get_http_client_factory",
        lambda: recording_factory,
    )

    response = client.post(
        "/convert/html-docx",
        files={"file": ("resume.html", BytesIO(b"<html><body><h1>Resume</h1></body></html>"), "text/html")},
    )

    assert response.status_code == 200
    assert response.headers["x-conversion-service"] == "html4docx"
    assert len(recording_factory.calls) == 1
    assert recording_factory.calls[0]["url"].endswith("/html4docx")
    assert _get_docx_paragraphs(response.content) == [
        "Via Marie Mutiangpili",
        "vmarvmar23@gmail.com | +63 905 590 4276",
        "Bataan, PH",
        "Professional Summary",
    ]


def test_html_docx_default_html4docx_keeps_horizontal_rule_paragraphs(client, monkeypatch):
    """Border-only paragraphs from HTML hr elements must survive whitespace cleanup."""
    from convert.utils import http_client

    mocked_docx = _build_docx_with_rule_paragraph()
    recording_factory = RecordingPyconvertFactory(mocked_docx)

    monkeypatch.setattr(
        http_client,
        "get_http_client_factory",
        lambda: recording_factory,
    )

    response = client.post(
        "/convert/html-docx",
        files={
            "file": (
                "resume.html",
                BytesIO(b"<html><body><h1>Header</h1><hr /><p>After header</p></body></html>"),
                "text/html",
            )
        },
    )

    assert response.status_code == 200
    assert response.headers["x-conversion-service"] == "html4docx"
    assert _get_docx_paragraphs(response.content) == ["Header", "", "After header"]

    with ZipFile(BytesIO(response.content)) as docx_zip:
        document_xml = docx_zip.read("word/document.xml").decode("utf-8")

    assert "<w:pBdr>" in document_xml
    assert "<w:bottom" in document_xml


def test_html_docx_libreoffice_uses_explicit_docx_filter(client, monkeypatch):
    """HTML to DOCX via LibreOffice should inject the filter and trim top blanks."""
    from convert.utils import conversion_core
    from convert.utils import conversion_lookup

    mocked_docx = _build_docx_with_paragraphs(
        [
            "",
            "",
            "Via Marie Mutiangpili",
            "vmarvmar23@gmail.com | +63 905 590 4276",
            "Bataan, PH",
        ]
    )
    recording_client = RecordingLibreOfficeClient(mocked_docx)

    async def fake_get_service_client(service, request):
        assert service == ConversionService.LIBREOFFICE
        return recording_client

    monkeypatch.setattr(conversion_core, "_get_service_client", fake_get_service_client)
    monkeypatch.setattr(
        conversion_lookup,
        "get_all_conversions",
        lambda *_args, **_kwargs: [(ConversionService.LIBREOFFICE, "HTML to Word")],
    )

    response = client.post(
        "/convert/html-docx",
        files={"file": ("resume.html", BytesIO(b"<html><body><p>Resume</p></body></html>"), "text/html")},
    )

    assert response.status_code == 200
    assert response.headers["x-conversion-service"] == "libreoffice"

    assert len(recording_client.calls) == 1
    call = recording_client.calls[0]
    assert call["url"].endswith("/request")
    assert ("convert-to", "docx") in call["data"]
    assert ("opts[]", "--filter=MS Word 2007 XML") in call["data"]
    assert _get_docx_paragraphs(response.content) == [
        "Via Marie Mutiangpili",
        "vmarvmar23@gmail.com | +63 905 590 4276",
        "Bataan, PH",
    ]