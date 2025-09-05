# File Validation Module

This module provides robust file type validation for the document conversion system.

## Features

- **Factory Pattern**: Easy-to-use factory method for validation
- **Format Support**: Validates PDF, DOCX, HTML, Markdown, Text, JSON, and TeX files
- **Efficient**: Fast validation with high confidence levels
- **Flexible HTML**: Supports both full HTML documents and content fragments
- **Error Handling**: Clear error messages for validation failures

## Usage

```python
from convert.validate import validate_file

# Basic validation
result = validate_file('/path/to/document.pdf', 'pdf')

# HTML with full document check
result = validate_file('/path/to/page.html', 'html', full=True)

# HTML content fragment
result = validate_file('/path/to/content.html', 'html', full=False)

# HTML with default validation (checks for valid tags and content)
result = validate_file('/path/to/content.html', 'html')
```

## Supported Formats

- **PDF**: Checks magic bytes, version, and EOF marker
- **DOCX**: Validates ZIP structure and required files
- **XLSX**: Validates ZIP structure and Excel workbook files
- **HTML**: Two modes - full document or content fragment
- **Markdown**: UTF-8 encoding and basic structure
- **Text**: UTF-8 encoding validation
- **JSON**: JSON parsing and structure validation
- **TeX**: LaTeX command and document structure checks

## Validation Rules

- Filesize of 0 always fails
- All files must be readable
- Format-specific validation with 90%+ confidence
- Clear error messages for debugging

## HTML Validation

### Full Mode (`full=True`)
- Requires `<html>` tag
- Requires `<body>` tag with content
- Validates proper document structure

### Content Mode (`full=False`)
- Requires at least one HTML tag
- Allows HTML fragments/snippets
- Validates presence of actual content

## Error Handling

```python
from convert.validate import validate_file, ValidationError

try:
    validate_file('/path/to/file.pdf', 'pdf')
except ValidationError as e:
    print(f"Validation failed: {e}")
```

## Testing

Run the test script to validate all supported formats:

```bash
cd proxy-service
python convert/validate/test_validation.py
```
