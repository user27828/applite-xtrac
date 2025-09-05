#!/usr/bin/env python3
"""
Sample file validator and creator for proxy-service tests.

This script checks for the existence of sample files in the fixtures directory
and creates basic content for any missing files.
"""

import os
from pathlib import Path

# Define sample files and their basic content
SAMPLE_FILES = {
    "sample.md": """# Sample Markdown Document

This is a sample markdown file for testing document conversions.

## Features

- Basic markdown formatting
- Multiple headings
- Simple text content
- Used for testing markdown to PDF, DOCX, and other conversions

## Content

This document contains typical markdown elements that can be converted to various formats.

### Lists

- Item 1
- Item 2
- Item 3

### Code

```python
print("Hello, World!")
```

### Links

[Sample Link](https://example.com)

---

*This is a test document for the applite-convert project.*
""",

    "sample.html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sample HTML Document</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
        }
        h1, h2, h3 {
            color: #333;
        }
        .highlight {
            background-color: #f0f0f0;
            padding: 10px;
            border-left: 4px solid #007acc;
        }
    </style>
</head>
<body>
    <h1>Sample HTML Document</h1>

    <p>This is a sample HTML file for testing web content conversions.</p>

    <h2>Features</h2>
    <ul>
        <li>HTML5 structure</li>
        <li>CSS styling</li>
        <li>Semantic elements</li>
        <li>Test content for conversions</li>
    </ul>

    <h2>Content Section</h2>
    <div class="highlight">
        <p>This document contains typical HTML elements that can be converted to various formats including PDF, DOCX, and Markdown.</p>
    </div>

    <h3>Lists</h3>
    <ol>
        <li>First item</li>
        <li>Second item</li>
        <li>Third item</li>
    </ol>

    <h3>Code Example</h3>
    <pre><code>&lt;html&gt;
&lt;head&gt;
    &lt;title&gt;Example&lt;/title&gt;
&lt;/head&gt;
&lt;body&gt;
    &lt;h1&gt;Hello World&lt;/h1&gt;
&lt;/body&gt;
&lt;/html&gt;</code></pre>

    <p><a href="https://example.com">Visit Example Website</a></p>

    <hr>
    <footer>
        <p><em>This is a test document for the applite-convert project.</em></p>
    </footer>
</body>
</html>""",

    "sample.txt": """Sample Text Document

This is a sample plain text file for testing document conversions.

Features:
- Plain text format
- Simple content
- No formatting
- Used for basic conversion tests

Content:
This document contains typical text content that can be converted to various formats including PDF, DOCX, and HTML.

Lists:
1. First item
2. Second item
3. Third item

Code:
print("Hello, World!")

Links:
https://example.com

---
This is a test document for the applite-convert project.""",

    "sample.latex": """\\documentclass{article}

\\usepackage[utf8]{inputenc}
\\usepackage[T1]{fontenc}
\\usepackage{amsmath}
\\usepackage{graphicx}
\\usepackage{hyperref}

\\title{Sample LaTeX Document}
\\author{Test Author}
\\date{\\today}

\\begin{document}

\\maketitle

\\section{Introduction}

This is a sample LaTeX file for testing academic document conversions.

\\section{Features}

\\begin{itemize}
\\item LaTeX formatting
\\item Mathematical expressions
\\item Cross-references
\\item Bibliography support
\\end{itemize}

\\section{Content}

This document contains typical LaTeX elements that can be converted to various formats including PDF, DOCX, and HTML.

\\subsection{Mathematics}

Here is a simple equation:
\\begin{equation}
E = mc^2
\\end{equation}

\\subsection{Code}

\\begin{verbatim}
def hello_world():
    print("Hello, World!")
\\end{verbatim}

\\section{Conclusion}

This is a test document for the applite-convert project.

\\end{document}""",

    "sample.tex": """\\documentclass{article}

\\usepackage[utf8]{inputenc}
\\usepackage[T1]{fontenc}

\\title{Sample TeX Document}
\\author{Test Author}

\\begin{document}

\\maketitle

\\section{Introduction}

This is a sample TeX file for testing document conversions.

\\section{Features}

\\begin{itemize}
\\item TeX formatting
\\item Basic document structure
\\item Simple content
\\end{itemize}

\\section{Content}

This document contains typical TeX elements.

\\subsection{Text}

Here is some sample text content.

\\subsection{Lists}

\\begin{enumerate}
\\item First item
\\item Second item
\\item Third item
\\end{enumerate}

\\section{Conclusion}

This is a test document for the applite-convert project.

\\end{document}"""
}

def main():
    """Main function to validate and create sample files."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    fixtures_dir.mkdir(exist_ok=True)

    print("🔍 Checking sample files in fixtures directory...")
    print(f"Fixtures directory: {fixtures_dir}")

    created_count = 0
    existing_count = 0

    for filename, content in SAMPLE_FILES.items():
        file_path = fixtures_dir / filename

        if file_path.exists():
            print(f"✅ {filename} - Already exists")
            existing_count += 1
        else:
            print(f"📝 {filename} - Creating...")
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✅ {filename} - Created successfully")
                created_count += 1
            except Exception as e:
                print(f"❌ {filename} - Failed to create: {e}")

    # Check for other sample files that might exist
    other_files = []
    for file_path in fixtures_dir.glob("sample.*"):
        filename = file_path.name
        if filename not in SAMPLE_FILES:
            other_files.append(filename)

    print(f"\n📊 Summary:")
    print(f"  Existing files: {existing_count}")
    print(f"  Created files: {created_count}")
    print(f"  Other files: {len(other_files)}")

    if other_files:
        print(f"  Other sample files found: {', '.join(other_files)}")

    total_files = existing_count + created_count + len(other_files)
    print(f"  Total sample files: {total_files}")

    if created_count > 0:
        print(f"\n🎉 Sample files created successfully!")
        print("You can now run the test suite.")
    else:
        print(f"\n✅ All basic sample files already exist.")
        print("You can run the test suite.")

if __name__ == "__main__":
    main()
