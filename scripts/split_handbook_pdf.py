"""Split the UGC handbook PDF into per-page JSON and Markdown (one-off source preparation).

    uv run python scripts/split_handbook_pdf.py

Reads data/raw/handbook/student_handbook_english.pdf and writes the .json and .md
next to it. The structured Markdown used by the pipelines
(student_handbook_english_structured.md) was edited by hand from that output.
"""

import json

import pymupdf4llm

from campusyamu.core.paths import HANDBOOK_PDF

pdf_path = HANDBOOK_PDF
json_path = pdf_path.with_suffix(".json")
markdown_path = pdf_path.with_suffix(".md")

page_chunks = pymupdf4llm.to_markdown(
    str(pdf_path),
    page_chunks=True
)

pages = [
    {
        "page": chunk["metadata"]["page_number"],
        "text": chunk["text"]
    }
    for chunk in page_chunks
]

with json_path.open("w", encoding="utf-8") as json_file:
    json.dump(pages, json_file, ensure_ascii=False, indent=2)

markdown_sections = ["# Student Handbook (English)"]

for page in pages:
    text = page["text"].strip() or "_No extractable text on this page._"
    markdown_sections.append(f"## Page {page['page']}\n\n{text}")

markdown_path.write_text(
    "\n\n".join(markdown_sections) + "\n",
    encoding="utf-8"
)

print(f"Saved {len(pages)} pages to {json_path}")
print(f"Saved Markdown to {markdown_path}")
