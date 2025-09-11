"""
Local conversion factory for applite-xtrac.

This module provides a factory pattern for local document conversions
that don't require external container services.
"""

import logging
from typing import Optional, Tuple, Dict, Any
from io import BytesIO
from fastapi import HTTPException

# Import centralized temp file manager
from ..utils.temp_file_manager import get_temp_manager

import pandas as pd
import xlrd
import openpyxl

try:
    from numbers_parser import Document
    NUMBERS_PARSER_AVAILABLE = True
except ImportError as e:
    Document = None
    NUMBERS_PARSER_AVAILABLE = False

logger = logging.getLogger(__name__)

# Log the availability of numbers-parser
if NUMBERS_PARSER_AVAILABLE:
    logger.info("numbers-parser successfully imported")
else:
    logger.warning("numbers-parser import failed")


class LocalConversionFactory:
    """
    Factory for local document conversions.

    Currently supports Excel (.xls, .xlsx), OpenDocument (.ods), and Apple Numbers (.numbers) to text/markdown conversions.
    """

    def __init__(self):
        """Initialize the conversion factory."""
        self._converters = {
            'excel': self._convert_excel
        }

    def convert(self, file_content: bytes, filename: str, input_format: str, output_format: str) -> Tuple[str, str, str]:
        """
        Convert a file using local processing.

        Args:
            file_content: Raw bytes of the input file
            filename: Original filename
            input_format: Input format (e.g., 'xlsx', 'xls', 'ods')
            output_format: Desired output format (e.g., 'md', 'txt')

        Returns:
            Tuple of (content, media_type, output_filename)

        Raises:
            HTTPException: If conversion fails or format is unsupported
        """
        try:
            # Determine converter based on input format
            if input_format in ['xlsx', 'xls', 'ods', 'numbers']:
                converter = self._converters['excel']
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported input format for local conversion: {input_format}")

            # Perform conversion
            return converter(file_content, filename, output_format)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Local conversion error: {e}")
            raise HTTPException(status_code=500, detail=f"Local conversion failed: {str(e)}")

    def _convert_excel(self, file_content: bytes, filename: str, output_format: str) -> Tuple[str, str, str]:
        """
        Convert Excel file to text or markdown format.

        Args:
            file_content: Raw bytes of the Excel file
            filename: Original filename
            output_format: Target format ('md' or 'txt')

        Returns:
            Tuple of (content, media_type, output_filename)
        """
        try:
            # Parse Excel file to DataFrame
            df = self._read_excel_file(file_content, filename)

            # Generate base filename
            base_name = filename.rsplit(".", 1)[0] if "." in filename else filename

            # Convert based on output format
            if output_format == "md":
                content = self._excel_to_markdown(df, base_name)
                media_type = "text/markdown"
            elif output_format == "txt":
                content = self._excel_to_text(df, base_name)
                media_type = "text/plain"
            elif output_format == "json":
                content = self._excel_to_json(df, base_name)
                media_type = "application/json"
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

    def _read_excel_file(self, file_content: bytes, filename: str) -> pd.DataFrame:
        """
        Read Excel/ODS/Numbers file content and return as pandas DataFrame.

        Args:
            file_content: Raw bytes of the Excel/ODS/Numbers file
            filename: Filename to determine format

        Returns:
            pandas DataFrame

        Raises:
            HTTPException: If file cannot be read
        """
        try:
            # Create BytesIO object for pandas
            buffer = BytesIO(file_content)

            # Determine file extension and engine
            if filename.lower().endswith('.xlsx'):
                engine = 'openpyxl'
            elif filename.lower().endswith('.xls'):
                engine = 'xlrd'
            elif filename.lower().endswith('.ods'):
                engine = 'odf'
            elif filename.lower().endswith('.numbers'):
                # Handle Apple Numbers files
                if not NUMBERS_PARSER_AVAILABLE or not Document:
                    raise HTTPException(status_code=503, detail="Numbers file support requires the 'numbers-parser' package. Please install it with: pip install numbers-parser")
                
                # Save to temporary file for numbers-parser using centralized manager
                manager = get_temp_manager("conversion")
                temp_file = manager.create_temp_file(
                    content=file_content,
                    extension='.numbers',
                    prefix="numbers_conversion"
                )
                temp_file_path = temp_file.path

                # Parse Numbers file
                doc = Document(temp_file_path)
                # Get the first sheet (or we could iterate through all sheets)
                if len(doc.sheets) == 0:
                    raise HTTPException(status_code=400, detail="Numbers file contains no sheets")
                
                sheet = doc.sheets[0]
                
                # Convert to DataFrame
                data = []
                headers = []
                
                # Get headers from first row if it exists
                if len(sheet.rows) > 0:
                    headers = [str(cell.value) if cell.value is not None else f"Column_{i}" for i, cell in enumerate(sheet.rows[0])]
                    data = [[cell.value for cell in row] for row in sheet.rows[1:]]
                else:
                    # Empty sheet
                    headers = ["Column_0"]
                    data = []
                
                df = pd.DataFrame(data, columns=headers)

                return df
            else:
                raise HTTPException(status_code=400, detail="Unsupported spreadsheet file format")

            # Read the file using pandas
            df = pd.read_excel(buffer, engine=engine)
            return df

        except Exception as e:
            logger.error(f"Error reading spreadsheet file: {e}")
            error_msg = str(e)
            
            # Provide more helpful error messages for common issues
            if "odfpy" in error_msg.lower():
                error_msg = "ODS file support requires the 'odfpy' package. Please install it with: pip install odfpy"
            elif "openpyxl" in error_msg.lower():
                error_msg = "XLSX file support requires the 'openpyxl' package. Please install it with: pip install openpyxl"
            elif "xlrd" in error_msg.lower():
                error_msg = "XLS file support requires the 'xlrd' package. Please install it with: pip install xlrd"
            elif "numbers_parser" in error_msg.lower() or "numbersparser" in error_msg.lower():
                error_msg = "Numbers file support requires the 'numbers-parser' package. Please install it with: pip install numbers-parser"
            
            raise HTTPException(status_code=400, detail=f"Failed to read spreadsheet file: {error_msg}")

    def _excel_to_markdown(self, df: pd.DataFrame, filename: str = "") -> str:
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

    def _excel_to_text(self, df: pd.DataFrame, filename: str = "") -> str:
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

    def _excel_to_json(self, df: pd.DataFrame, filename: str = "") -> str:
        """
        Convert a pandas DataFrame to JSON format.

        Args:
            df: DataFrame containing the Excel data
            filename: Original filename (not used in JSON conversion)

        Returns:
            JSON formatted string
        """
        if df.empty:
            return "{}"  # Return empty JSON object for empty DataFrame

        # Convert DataFrame to JSON
        return df.to_json(orient="records")


# Global factory instance
factory = LocalConversionFactory()


def convert_file_locally(file_content: bytes, filename: str, input_format: str, output_format: str) -> Tuple[str, str, str]:
    """
    Convenience function to convert a file using the local factory.

    Args:
        file_content: Raw bytes of the input file
        filename: Original filename
        input_format: Input format (e.g., 'xlsx', 'xls', 'ods')
        output_format: Desired output format (e.g., 'md', 'txt')

    Returns:
        Tuple of (content, media_type, output_filename)
    """
    return factory.convert(file_content, filename, input_format, output_format)
