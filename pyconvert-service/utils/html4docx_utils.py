from __future__ import annotations

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
import re
import xml.etree.ElementTree as ET


HTML4DOCX_DEFAULT_PARAGRAPH_STYLE = "Body Text"

HTML4DOCX_KEEP_STYLE_NAMES = {
    "Normal",
    "Body Text",
    "Default Paragraph Font",
    "No Spacing",
    "Title",
    "Subtitle",
    "Heading 1",
    "Heading 2",
    "Heading 3",
    "Heading 4",
    "Heading 5",
    "Heading 6",
    "Heading 7",
    "Heading 8",
    "Heading 9",
    "List Paragraph",
    "List Bullet",
    "List Bullet 2",
    "List Bullet 3",
    "List Number",
    "List Number 2",
    "List Number 3",
    "Caption",
    "Quote",
    "Hyperlink",
    "Table Grid",
}

HTML4DOCX_STYLE_FONT_SIZES_PT = {
    "Heading 1": 16,
    "Heading 2": 14,
    "Heading 3": 12,
    "Heading 4": 12,
    "Heading 5": 12,
    "Heading 6": 12,
    "Heading 7": 12,
    "Heading 8": 12,
    "Heading 9": 12,
}

HTML4DOCX_NUMBERING_STYLE_RULES = {
    "ListBullet": {"left": "720", "hanging": "480", "lvlText": "•", "numFmt": "bullet", "keepRFonts": False},
    "ListBullet2": {"left": "1440", "hanging": "480", "lvlText": "–", "numFmt": "bullet", "keepRFonts": False},
    "ListBullet3": {"left": "2160", "hanging": "480", "lvlText": "•", "numFmt": "bullet", "keepRFonts": False},
    "ListNumber": {"left": "720", "hanging": "480", "lvlText": "%1.", "numFmt": "decimal", "keepRFonts": True},
    "ListNumber2": {"left": "1440", "hanging": "480", "lvlText": "%1.", "numFmt": "decimal", "keepRFonts": True},
    "ListNumber3": {"left": "2160", "hanging": "480", "lvlText": "%1.", "numFmt": "decimal", "keepRFonts": True},
}

WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"
WP14_NS = "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
ET.register_namespace("w", WORD_NS)
ET.register_namespace("mc", MC_NS)
ET.register_namespace("w14", W14_NS)
ET.register_namespace("wp14", WP14_NS)

HTML4DOCX_INHERITED_FONT_STYLE_NAMES = {
    "Normal",
    "Body Text",
    "List Paragraph",
    "List Bullet",
    "List Bullet 2",
    "List Bullet 3",
    "List Number",
    "List Number 2",
    "List Number 3",
}

HTML4DOCX_STYLE_PARAGRAPH_SPACING_PT = {
    "Body Text": {"before": 9, "after": 9},
    "List Paragraph": {"before": 0, "after": 0},
    "List Bullet": {"before": 0, "after": 0},
    "List Bullet 2": {"before": 0, "after": 0},
    "List Bullet 3": {"before": 0, "after": 0},
    "List Number": {"before": 0, "after": 0},
    "List Number 2": {"before": 0, "after": 0},
    "List Number 3": {"before": 0, "after": 0},
    "Heading 1": {"before": 24, "after": 0},
    "Heading 2": {"before": 10, "after": 0},
    "Heading 3": {"before": 10, "after": 0},
}

HTML4DOCX_STYLE_BASES = {
    "Body Text": "Normal",
    "List Bullet": "Body Text",
    "List Bullet 2": "Body Text",
    "List Bullet 3": "Body Text",
    "List Number": "Body Text",
    "List Number 2": "Body Text",
    "List Number 3": "Body Text",
}

HTML4DOCX_DEFAULT_FONT_SIZE_PT = 12


def _get_or_add_child(parent, tag: str):
    child = parent.find(qn(tag))

    if child is None:
        child = OxmlElement(tag)
        parent.append(child)

    return child


def set_html4docx_doc_defaults(document, font_size_pt: int) -> None:
    """Set document-level default run sizes so unstyled text matches Pandoc."""
    styles_element = document.styles.element
    doc_defaults = styles_element.find(qn("w:docDefaults"))

    if doc_defaults is None:
        doc_defaults = OxmlElement("w:docDefaults")
        styles_element.insert(0, doc_defaults)

    rpr_default = _get_or_add_child(doc_defaults, "w:rPrDefault")
    rpr = _get_or_add_child(rpr_default, "w:rPr")
    half_points = str(font_size_pt * 2)

    for tag in ("w:sz", "w:szCs"):
        size_element = _get_or_add_child(rpr, tag)
        size_element.set(qn("w:val"), half_points)


def clear_html4docx_docdefault_line_spacing(document) -> None:
    """Remove template-default line spacing so paragraphs inherit Pandoc-like height."""
    styles_element = document.styles.element
    doc_defaults = styles_element.find(qn("w:docDefaults"))

    if doc_defaults is None:
        return

    ppr_default = doc_defaults.find(qn("w:pPrDefault"))

    if ppr_default is None:
        return

    ppr = ppr_default.find(qn("w:pPr"))

    if ppr is None:
        return

    spacing = ppr.find(qn("w:spacing"))

    if spacing is None:
        return

    for attribute_name in ("line", "lineRule", "beforeLines", "afterLines"):
        spacing.attrib.pop(qn(f"w:{attribute_name}"), None)


def remove_html4docx_doc_grid(document) -> None:
    """Drop the default section docGrid so Word does not enforce extra line pitch."""
    for section in document.sections:
        sect_pr = section._sectPr
        doc_grid = sect_pr.find(qn("w:docGrid"))

        if doc_grid is not None:
            sect_pr.remove(doc_grid)


def clear_html4docx_inherited_style_sizes(document) -> None:
    styles = document.styles

    for style_name in HTML4DOCX_INHERITED_FONT_STYLE_NAMES:
        try:
            style_element = styles[style_name].element
        except KeyError:
            continue

        rpr = style_element.find(qn("w:rPr"))

        if rpr is None:
            continue

        for tag in ("w:sz", "w:szCs"):
            size_element = rpr.find(qn(tag))

            if size_element is not None:
                rpr.remove(size_element)


def tune_html4docx_settings(document) -> None:
    """Reduce settings/template drift so Word renders closer to Pandoc output."""
    settings_element = document.settings.element
    compat = settings_element.find(qn("w:compat"))

    if compat is not None:
        for compat_setting in list(compat.findall(qn("w:compatSetting"))):
            compat.remove(compat_setting)

        if len(compat) == 0:
            settings_element.remove(compat)

    zoom = settings_element.find(qn("w:zoom"))

    if zoom is None:
        zoom = OxmlElement("w:zoom")
        settings_element.insert(0, zoom)

    zoom.set(qn("w:percent"), "100")


def apply_html4docx_style_bases(document) -> None:
    styles = document.styles

    for style_name, base_style_name in HTML4DOCX_STYLE_BASES.items():
        try:
            styles[style_name].base_style = styles[base_style_name]
        except KeyError:
            continue


def apply_html4docx_paragraph_spacing(document) -> None:
    styles = document.styles

    for style_name, spacing in HTML4DOCX_STYLE_PARAGRAPH_SPACING_PT.items():
        try:
            paragraph_format = styles[style_name].paragraph_format
        except KeyError:
            continue

        before = spacing.get("before")
        after = spacing.get("after")

        if before is not None:
            paragraph_format.space_before = Pt(before)

        if after is not None:
            paragraph_format.space_after = Pt(after)


def apply_html4docx_font_tuning(document) -> None:
    """Tune built-in python-docx styles toward Pandoc's HTML->DOCX defaults."""
    set_html4docx_doc_defaults(document, HTML4DOCX_DEFAULT_FONT_SIZE_PT)
    clear_html4docx_docdefault_line_spacing(document)
    remove_html4docx_doc_grid(document)
    clear_html4docx_inherited_style_sizes(document)
    tune_html4docx_settings(document)
    apply_html4docx_style_bases(document)
    apply_html4docx_paragraph_spacing(document)
    styles = document.styles

    for style_name, font_size_pt in HTML4DOCX_STYLE_FONT_SIZES_PT.items():
        try:
            styles[style_name].font.size = Pt(font_size_pt)
        except KeyError:
            continue


def prune_html4docx_styles(document) -> None:
    """Drop unused style definitions to keep html4docx output closer to Pandoc size."""
    styles = document.styles

    for style in list(styles):
        if style.name in HTML4DOCX_KEEP_STYLE_NAMES:
            continue

        try:
            style.delete()
        except Exception:
            continue


def sync_docx_styles_with_effects(docx_bytes: bytes) -> bytes:
    """Mirror styles.xml into stylesWithEffects.xml to avoid stale template styling."""
    source_buffer = BytesIO(docx_bytes)

    with ZipFile(source_buffer, "r") as source_zip:
        names = source_zip.namelist()

        if "word/styles.xml" not in names or "word/stylesWithEffects.xml" not in names:
            return docx_bytes

        styles_xml = source_zip.read("word/styles.xml")
        output_buffer = BytesIO()

        with ZipFile(output_buffer, "w", compression=ZIP_DEFLATED) as output_zip:
            for entry in source_zip.infolist():
                payload = styles_xml if entry.filename == "word/stylesWithEffects.xml" else source_zip.read(entry.filename)
                output_zip.writestr(entry, payload)

    return output_buffer.getvalue()


def _collect_used_xml_namespaces(root: ET.Element) -> set[str]:
    namespaces: set[str] = set()

    for element in root.iter():
        if element.tag.startswith("{"):
            namespaces.add(element.tag[1:].split("}", 1)[0])

        for attribute_name in element.attrib:
            if attribute_name.startswith("{"):
                namespaces.add(attribute_name[1:].split("}", 1)[0])

    return namespaces


def _normalize_markup_compatibility_attributes(root: ET.Element, original_xml: bytes) -> None:
    ignorable_attr_name = f"{{{MC_NS}}}Ignorable"
    ignorable_value = root.get(ignorable_attr_name)

    if not ignorable_value:
        return

    root_start_tag = original_xml.decode("utf-8", errors="ignore").split(">", 1)[0]
    prefix_to_uri = {
        prefix: uri
        for prefix, uri in re.findall(r'xmlns:([A-Za-z_][\w.-]*)="([^"]+)"', root_start_tag)
    }
    used_namespaces = _collect_used_xml_namespaces(root)
    kept_prefixes = [
        prefix
        for prefix in ignorable_value.split()
        if prefix_to_uri.get(prefix) in used_namespaces
    ]

    if kept_prefixes:
        root.set(ignorable_attr_name, " ".join(kept_prefixes))
        return

    root.attrib.pop(ignorable_attr_name, None)


def normalize_docx_numbering_for_pandoc(docx_bytes: bytes) -> bytes:
    """Adjust list numbering geometry toward Pandoc defaults."""
    source_buffer = BytesIO(docx_bytes)

    with ZipFile(source_buffer, "r") as source_zip:
        if "word/numbering.xml" not in source_zip.namelist():
            return docx_bytes

        original_numbering_xml = source_zip.read("word/numbering.xml")
        numbering_root = ET.fromstring(original_numbering_xml)
        ignorable_attr_name = f"{{{MC_NS}}}Ignorable"
        original_ignorable = numbering_root.get(ignorable_attr_name)
        changed = False

        for abstract_num in numbering_root.findall(f"{{{WORD_NS}}}abstractNum"):
            for level in abstract_num.findall(f"{{{WORD_NS}}}lvl"):
                style_name = None
                p_style = level.find(f"{{{WORD_NS}}}pStyle")

                if p_style is not None:
                    style_name = p_style.get(f"{{{WORD_NS}}}val")

                if style_name not in HTML4DOCX_NUMBERING_STYLE_RULES:
                    continue

                rule = HTML4DOCX_NUMBERING_STYLE_RULES[style_name]
                ppr = level.find(f"{{{WORD_NS}}}pPr")

                if ppr is None:
                    ppr = ET.SubElement(level, f"{{{WORD_NS}}}pPr")

                tabs = ppr.find(f"{{{WORD_NS}}}tabs")
                if tabs is not None:
                    ppr.remove(tabs)

                ind = ppr.find(f"{{{WORD_NS}}}ind")
                if ind is None:
                    ind = ET.SubElement(ppr, f"{{{WORD_NS}}}ind")

                ind.set(f"{{{WORD_NS}}}left", rule["left"])
                ind.set(f"{{{WORD_NS}}}hanging", rule["hanging"])
                ind.attrib.pop(f"{{{WORD_NS}}}firstLine", None)

                num_fmt = level.find(f"{{{WORD_NS}}}numFmt")
                if num_fmt is None:
                    num_fmt = ET.SubElement(level, f"{{{WORD_NS}}}numFmt")
                num_fmt.set(f"{{{WORD_NS}}}val", rule["numFmt"])

                lvl_text = level.find(f"{{{WORD_NS}}}lvlText")
                if lvl_text is None:
                    lvl_text = ET.SubElement(level, f"{{{WORD_NS}}}lvlText")
                lvl_text.set(f"{{{WORD_NS}}}val", rule["lvlText"])

                rpr = level.find(f"{{{WORD_NS}}}rPr")
                if rpr is not None and not rule["keepRFonts"]:
                    rfonts = rpr.find(f"{{{WORD_NS}}}rFonts")
                    if rfonts is not None:
                        rpr.remove(rfonts)

                changed = True

        _normalize_markup_compatibility_attributes(numbering_root, original_numbering_xml)
        normalized_ignorable = numbering_root.get(ignorable_attr_name)

        if not changed and original_ignorable == normalized_ignorable:
            return docx_bytes

        output_buffer = BytesIO()
        numbering_xml = ET.tostring(numbering_root, encoding="utf-8", xml_declaration=True)

        with ZipFile(output_buffer, "w", compression=ZIP_DEFLATED) as output_zip:
            for entry in source_zip.infolist():
                payload = numbering_xml if entry.filename == "word/numbering.xml" else source_zip.read(entry.filename)
                output_zip.writestr(entry, payload)

    return output_buffer.getvalue()