"""Optional Gemini 2.5 Flash extraction with deterministic offline fallback.

The fallback reads explicit invoice IDs and monetary claims, without guessing
unreferenced invoices. Image-only PDFs return an actionable validation error.
"""

import io
import json
import os
import re
import httpx
from .models import Remittance, to_cents

INVOICE_PATTERN = r"\bINV(?:OICE)?[- ][A-Z0-9]+(?:-[A-Z0-9]+)*\b"
AMOUNT = r"\$\s*([\d,]+(?:\.\d{1,2})?)"


def regex_parse(text, document_id="uploaded-remittance", deposit_id=None):
    customer = re.search(r"(?:customer|payer|from)\s*:\s*([^\n;]+)", text, re.I)
    references = {}
    for line in text.splitlines():
        ids = list(re.finditer(INVOICE_PATTERN, line, re.I))
        for index, hit in enumerate(ids):
            invoice_id = hit[0].upper().replace(" ", "-")
            start = 0 if index == 0 else hit.start()
            end = ids[index + 1].start() if index + 1 < len(ids) else len(line)
            segment = line[start:end]
            amounts = re.findall(AMOUNT, segment)
            deduction = 0
            paid = None
            claim = re.search(
                r"(?:deduct(?:ion|ed)?|debit\s+memo|short[ -]?pay|claim|damag|crack|credit\s+claim)",
                segment,
                re.I,
            )
            # One amount can be unambiguously attached to one referenced invoice.
            if len(amounts) == 1:
                if claim:
                    deduction = to_cents(amounts[0])
                elif re.search(r"paid|payment|remit", segment, re.I):
                    paid = to_cents(amounts[0])
            references[invoice_id] = {
                "invoice_id": invoice_id,
                "paid_amount_cents": paid,
                "deduction_cents": deduction,
                "reason_code": (
                    "DAMAGED_GOODS"
                    if re.search(r"damag|crack", segment, re.I)
                    else "DOCUMENTED_CLAIM"
                ),
                "note": segment.strip(),
            }
    return Remittance(
        document_id=document_id,
        deposit_id=deposit_id,
        customer_name=customer[1].strip() if customer else "",
        raw_text=text,
        referenced_invoices=list(references.values()),
    )


def extract_text_pdf(content):
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            if len(pdf.pages) > 100:
                raise ValueError("PDF exceeds 100 pages; upload a smaller remittance")
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(
            "Cannot read this PDF; upload a valid text-based PDF or paste the remittance text"
        ) from exc
    if not text.strip():
        raise ValueError(
            "No readable text in PDF. Paste the remittance text or upload a text-based PDF"
        )
    return text


def parse_remittance(text, document_id="uploaded-remittance", deposit_id=None):
    if not text.strip():
        raise ValueError("Remittance is empty; paste text or upload a text-based PDF")
    fallback = regex_parse(text, document_id, deposit_id)
    key = os.environ.get("GEMINI_API_KEY")
    warning = None
    if key:
        try:
            schema = {
                "customer_name": "",
                "referenced_invoices": [
                    {
                        "invoice_id": "exact ID",
                        "paid_amount_cents": None,
                        "deduction_cents": 0,
                        "reason_code": "",
                        "note": "exact supporting text",
                    }
                ],
            }
            response = httpx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
                headers={"x-goog-api-key": key},
                timeout=15,
                json={
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": "Extract remittance facts. Use integer cents. Never invent invoice IDs or amounts. Return JSON only using this schema: "
                                    + json.dumps(schema)
                                    + "\nSource:\n"
                                    + text
                                }
                            ]
                        }
                    ],
                    "generationConfig": {
                        "responseMimeType": "application/json",
                        "temperature": 0,
                    },
                },
            )
            response.raise_for_status()
            data = json.loads(
                response.json()["candidates"][0]["content"]["parts"][0]["text"]
            )
            parsed = Remittance(
                **data, document_id=document_id, deposit_id=deposit_id, raw_text=text
            )
            if any(
                ref.invoice_id.lower() not in text.lower()
                for ref in parsed.referenced_invoices
            ):
                raise ValueError("Extracted invoice was not present in source")
            return parsed, "gemini-2.5-flash", None
        except Exception:
            warning = "Gemini unavailable or extraction invalid; deterministic offline parser used."
    if not fallback.referenced_invoices:
        warning = "No explicit invoice IDs found. Review the source and add exact invoice references."
    return fallback, "deterministic-regex", warning
