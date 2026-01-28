"""Invoice extractor using PaddleOCR and GitHub Copilot SDK."""

import asyncio
import json
import os
from pathlib import Path
from dataclasses import dataclass

# Suppress PaddleOCR connectivity check warnings
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"

from paddleocr import PaddleOCR
from copilot import CopilotClient


@dataclass
class InvoiceData:
    """Extracted invoice data."""

    arbeitspreis: float | None = None  # Price per MWh in CHF
    leistungspreis: float | None = None  # Leistungspreis net amount in CHF
    co2_abgabe: float | None = None  # CO2 fee in CHF (excl. MwSt.)
    raw_text: str = ""


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract text from PDF using PaddleOCR's native PDF support.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Extracted text as a single string
    """
    # Initialize PaddleOCR with German/Latin language support
    # PaddleOCR 3.x uses predict() method and new parameter names
    ocr = PaddleOCR(use_textline_orientation=True, lang="german")

    all_text = []

    # PaddleOCR 3.x uses predict() which returns a generator of OCRResult objects
    # Each OCRResult is dict-like with 'rec_texts' containing recognized text lines
    for page_result in ocr.predict(str(pdf_path)):
        if page_result and "rec_texts" in page_result:
            texts = page_result["rec_texts"]
            if texts:
                all_text.extend(texts)

    return "\n".join(all_text)


async def parse_invoice_with_ai(ocr_text: str) -> dict:
    """
    Use Copilot SDK to intelligently parse invoice text.

    Args:
        ocr_text: Raw OCR text from the invoice

    Returns:
        Dictionary with extracted values
    """
    client = CopilotClient()
    await client.start()

    session = await client.create_session({"model": "gpt-4o"})

    prompt = f"""You are extracting specific values from a Swiss district heating (Fernwärme) invoice.

Here is the OCR text from the invoice:

---
{ocr_text}
---

Please extract these three values and respond ONLY with a JSON object (no markdown, no explanation):

1. "arbeitspreis": The unit price per MWh in CHF for "Arbeitspreis". 
   Look for the "Preis" column value (NOT the Nettobetrag which is the total).

2. "leistungspreis": The TOTAL Nettobetrag for "FW Leistungspreis" in CHF.
   This is the total amount (e.g., 435.75), NOT the monthly unit price (e.g., 145.25).
   The line looks like: "FW Leistungspreis 20.00 kW  3  Mt  145.25  435.75"
   Extract 435.75 (the Nettobetrag total), not 145.25 (the unit price).

3. "co2_abgabe": The total CO2-Abgabe amount in CHF excluding MwSt.
   This is the sum of CO2 charges, typically shown in the Wärme section summary (e.g., 17.93).

Respond with JSON like: {{"arbeitspreis": 54.00, "leistungspreis": 435.75, "co2_abgabe": 17.93}}

If a value cannot be found, use null.
"""

    done = asyncio.Event()
    response_content = []

    def on_event(event):
        if event.type.value == "assistant.message":
            response_content.append(event.data.content)
            done.set()
        elif event.type.value == "session.idle":
            done.set()

    session.on(on_event)
    await session.send({"prompt": prompt})
    await done.wait()

    await session.destroy()
    await client.stop()

    # Parse the JSON response
    response_text = response_content[0] if response_content else "{}"

    # Clean up response (remove markdown code blocks if present)
    response_text = response_text.strip()
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return {"arbeitspreis": None, "leistungspreis": None, "co2_abgabe": None}


def extract_invoice_data(pdf_path: Path) -> InvoiceData:
    """
    Extract invoice data from a PDF file.

    Args:
        pdf_path: Path to the PDF invoice

    Returns:
        InvoiceData with extracted values
    """
    # Step 1: Extract text with OCR
    raw_text = extract_text_from_pdf(pdf_path)

    # Step 2: Parse with AI
    parsed = asyncio.run(parse_invoice_with_ai(raw_text))

    return InvoiceData(
        arbeitspreis=parsed.get("arbeitspreis"),
        leistungspreis=parsed.get("leistungspreis"),
        co2_abgabe=parsed.get("co2_abgabe"),
        raw_text=raw_text,
    )
