"""Invoice extractor using native PDF text extraction and GitHub Copilot SDK."""

import asyncio
import json
from pathlib import Path
from dataclasses import dataclass

import pdfplumber
from copilot import CopilotClient
from copilot.session import PermissionHandler


@dataclass
class InvoiceData:
    """Extracted invoice data."""

    arbeitspreis: float | None = None  # Price per MWh in CHF
    leistungspreis: float | None = None  # Leistungspreis net amount in CHF
    co2_abgabe: float | None = None  # CO2 fee in CHF (excl. MwSt.)
    raw_text: str = ""


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract text from a born-digital PDF, preserving layout.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Extracted text as a single string
    """
    pages: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(layout=True) or ""
            if text.strip():
                pages.append(text)
    return "\n".join(pages)


async def parse_invoice_with_ai(invoice_text: str) -> dict:
    """
    Use Copilot SDK to intelligently parse invoice text.

    Args:
        invoice_text: Raw text extracted from the invoice PDF

    Returns:
        Dictionary with extracted values
    """
    client = CopilotClient()
    await client.start()

    session = await client.create_session(
        on_permission_request=PermissionHandler.approve_all,
        model="gpt-5-mini",
    )

    prompt = f"""You are extracting specific values from a Swiss district heating (Fernwärme) invoice.

Here is the text from the invoice:

---
{invoice_text}
---

Please extract these three values and respond ONLY with a JSON object (no markdown, no explanation):

1. "arbeitspreis": The unit price per MWh in CHF for "Arbeitspreis".
   Look for the "Preis" column value (NOT the Nettobetrag which is the total).

2. "leistungspreis": The UNIT PRICE for "FW Leistungspreis" in CHF (the "Preis" column).
   IMPORTANT: This is the monthly price (e.g., 145.25), NOT the total Nettobetrag (e.g., 435.75).
   The line looks like: "FW Leistungspreis 20.00 kW  3  Mt  145.25  435.75"
   Extract 145.25 (the price), not 435.75 (the total).

3. "co2_abgabe": The total CO2-Abgabe amount in CHF excluding MwSt.
   This is the sum of CO2 charges, typically shown in the Wärme section summary (e.g., 17.93).

Respond with JSON like: {{"arbeitspreis": 54.00, "leistungspreis": 145.25, "co2_abgabe": 17.93}}

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
    await session.send(prompt)
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
    raw_text = extract_text_from_pdf(pdf_path)
    parsed = asyncio.run(parse_invoice_with_ai(raw_text))

    return InvoiceData(
        arbeitspreis=parsed.get("arbeitspreis"),
        leistungspreis=parsed.get("leistungspreis"),
        co2_abgabe=parsed.get("co2_abgabe"),
        raw_text=raw_text,
    )
