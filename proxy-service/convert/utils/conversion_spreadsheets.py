"""
Utility functions for Excel document conversion processing.

This module contains shared utilities for processing Excel files
and converting them to various formats.
"""

import logging
from typing import Optional
from io import BytesIO
from fastapi import HTTPException

import pandas as pd
import xlrd
import openpyxl

logger = logging.getLogger(__name__)


def excel_to_markdown(df, filename: str = "") -> str:
    """
    Convert a pandas DataFrame to Markdown table format.

    Args:
        df: DataFrame containing the Excel data
        filename: Original filename for header

    Returns:
        Markdown formatted string
    """
    if df.empty:
        return "# Empty Excel File\n\nNo data found in the Excel file."

    # Create header
    header = f"# {filename or 'Excel Data'}\n\n" if filename else ""

    # Convert DataFrame to markdown table
    # First, clean column names
    df.columns = [str(col).strip() for col in df.columns]

    # Convert all data to strings and handle NaN values
    df = df.fillna('')
    df = df.astype(str)

    # Create markdown table
    markdown_lines = []

    # Header row
    markdown_lines.append("| " + " | ".join(df.columns) + " |")

    # Separator row
    markdown_lines.append("| " + " | ".join(["---"] * len(df.columns)) + " |")

    # Data rows
    for _, row in df.iterrows():
        markdown_lines.append("| " + " | ".join(str(val).replace('|', '\\|') for val in row) + " |")

    return header + "\n".join(markdown_lines)


def excel_to_text(df, filename: str = "") -> str:
    """
    Convert a pandas DataFrame to plain text format.

    Args:
        df: DataFrame containing the Excel data
        filename: Original filename for header

    Returns:
        Plain text formatted string
    """
    if df.empty:
        return f"{filename or 'Excel Data'}\n\nNo data found in the Excel file."

    # Create header
    header = f"{filename or 'Excel Data'}\n{'=' * 50}\n\n" if filename else ""

    # Convert DataFrame to text format
    # Clean column names
    df.columns = [str(col).strip() for col in df.columns]

    # Convert all data to strings and handle NaN values
    df = df.fillna('')
    df = df.astype(str)

    text_lines = []

    # Add column headers
    text_lines.append("\t".join(df.columns))
    text_lines.append("-" * 50)

    # Add data rows
    for _, row in df.iterrows():
        text_lines.append("\t".join(str(val) for val in row))

    return header + "\n".join(text_lines)


def read_excel_file(file_content: bytes, filename: str):
    """
    Read Excel file content and return as pandas DataFrame.

    Args:
        file_content: Raw bytes of the Excel file
        filename: Filename to determine format

    Returns:
        pandas DataFrame
    """
    try:
        # Create BytesIO object for pandas
        buffer = BytesIO(file_content)

        # Determine file extension
        if filename.lower().endswith('.xlsx'):
            engine = 'openpyxl'
        elif filename.lower().endswith('.xls'):
            engine = 'xlrd'
        else:
            raise HTTPException(status_code=400, detail="Unsupported Excel file format")

        # Read Excel file
        df = pd.read_excel(buffer, engine=engine)

        return df

    except Exception as e:
        logger.error(f"Error reading Excel file: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to read Excel file: {str(e)}")


def convert_excel_to_format(file_content: bytes, filename: str, output_format: str):
    """
    Convert Excel file content to Markdown or Text format.

    Args:
        file_content: Raw bytes of the Excel file
        filename: Original filename
        output_format: Target format ('md' or 'txt')

    Returns:
        Tuple of (content, media_type, output_filename)
    """
    try:
        # Parse Excel file to DataFrame
        df = read_excel_file(file_content, filename)

        # Generate base filename
        base_name = filename.rsplit(".", 1)[0] if "." in filename else filename

        # Convert based on output format
        if output_format == "md":
            content = excel_to_markdown(df, base_name)
            media_type = "text/markdown"
        elif output_format == "txt":
            content = excel_to_text(df, base_name)
            media_type = "text/plain"
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported output format: {output_format}")

        # Generate output filename
        output_filename = f"{base_name}.{output_format}"

        return content, media_type, output_filename

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Excel conversion error: {e}")
        raise HTTPException(status_code=500, detail=f"Excel conversion failed: {str(e)}")
