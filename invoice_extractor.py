"""Invoice extractor using PaddleOCR and GitHub Copilot SDK."""

import asyncio
import json
import tempfile
from pathlib import Path
from dataclasses import dataclass

from paddleocr import PaddleOCR
from pdf2image import convert_from_path
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
    Extract text from PDF using PaddleOCR.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Extracted text as a single string
    """
    # Convert PDF to images
    images = convert_from_path(pdf_path)

    # Initialize PaddleOCR with German language support
    ocr = PaddleOCR(use_angle_cls=True, lang="german", show_log=False)

    all_text = []

    for i, image in enumerate(images):
        # Save image temporarily for PaddleOCR
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            temp_path = tmp.name
            image.save(temp_path, "PNG")

        # Run OCR
        result = ocr.ocr(temp_path, cls=True)

        # Extract text from result
        if result and result[0]:
            for line in result[0]:
                if line[1]:  # Has text
                    text = line[1][0]
                    all_text.append(text)

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

1. "arbeitspreis": The "Arbeitspreis" price per MWh in CHF. Look for "Preis CHF" in the Arbeitspreis section.
2. "leistungspreis": The "FW Leistungspreis" Nettobetrag in CHF. Look for the net amount for Leistungspreis.
3. "co2_abgabe": The "CO2-Abgabe" amount in CHF excluding MwSt. Look for the CO2 fee amount.

Respond with JSON like: {{"arbeitspreis": 49.00, "leistungspreis": 145.25, "co2_abgabe": 0.16}}

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
