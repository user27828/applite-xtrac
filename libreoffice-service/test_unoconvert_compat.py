"""Regression tests for the upgraded unoserver compatibility bridge."""

from unoconvert_compat import translate_arguments


def test_translate_arguments_replaces_legacy_interface_flag():
    assert translate_arguments(
        ["--interface", "127.0.0.1", "--port", "2003", "input.odt", "output.pdf"]
    ) == ["--host", "127.0.0.1", "--port", "2003", "input.odt", "output.pdf"]


def test_translate_arguments_preserves_equals_form_and_other_options():
    assert translate_arguments(
        [
            "--interface=127.0.0.1",
            "--output-filter=writer_pdf_Export",
            "input.odt",
            "output.pdf",
        ]
    ) == [
        "--host=127.0.0.1",
        "--output-filter=writer_pdf_Export",
        "input.odt",
        "output.pdf",
    ]
