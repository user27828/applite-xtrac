"""Helpers for rendering image inputs as printable HTML for PDF generation."""

import base64
from io import BytesIO
from typing import List

from fastapi import HTTPException

try:
    from PIL import Image, ImageSequence
    PIL_AVAILABLE = True
except ImportError:
    Image = None
    ImageSequence = None
    PIL_AVAILABLE = False

try:
    import pillow_heif  # type: ignore[import-not-found]
    PILLOW_HEIF_AVAILABLE = True
    if PIL_AVAILABLE:
        pillow_heif.register_heif_opener()
except ImportError:
    pillow_heif = None
    PILLOW_HEIF_AVAILABLE = False


def _ensure_image_support(input_format: str) -> None:
    if not PIL_AVAILABLE:
        raise HTTPException(status_code=503, detail="Image to PDF conversion requires Pillow")
    if input_format == "heic" and not PILLOW_HEIF_AVAILABLE:
        raise HTTPException(status_code=503, detail="HEIC to PDF conversion requires pillow-heif")


def _image_pages_to_png_data_uris(file_content: bytes, input_format: str) -> List[str]:
    _ensure_image_support(input_format)

    try:
        image = Image.open(BytesIO(file_content))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to read image input: {exc}") from exc

    frames = []
    iterator = ImageSequence.Iterator(image) if getattr(image, "n_frames", 1) > 1 else [image]
    for frame in iterator:
        normalized = frame.convert("RGBA")
        output = BytesIO()
        normalized.save(output, format="PNG")
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        frames.append(f"data:image/png;base64,{encoded}")

    if not frames:
        raise HTTPException(status_code=400, detail="No renderable image frames found")

    return frames


def build_image_pdf_html(file_content: bytes, filename: str, input_format: str) -> str:
    """Wrap one or more image frames in printable HTML for PDF rendering."""
    image_pages = _image_pages_to_png_data_uris(file_content, input_format)
    sections = []
    for page_number, data_uri in enumerate(image_pages, start=1):
        sections.append(
            f'''<section class="page">\n  <img src="{data_uri}" alt="{filename} page {page_number}">\n</section>'''
        )

    body = "\n".join(sections)
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{filename}</title>
  <style>
    @page {{
      size: A4;
      margin: 12mm;
    }}

    html, body {{
      margin: 0;
      padding: 0;
      background: #fff;
    }}

    body {{
      font-family: sans-serif;
    }}

    .page {{
      min-height: calc(297mm - 24mm);
      display: flex;
      align-items: center;
      justify-content: center;
      page-break-after: always;
      break-after: page;
    }}

    .page:last-child {{
      page-break-after: auto;
      break-after: auto;
    }}

    img {{
      display: block;
      max-width: 100%;
      max-height: calc(297mm - 24mm);
      object-fit: contain;
      margin: 0 auto;
    }}
  </style>
</head>
<body>
{body}
</body>
</html>'''
