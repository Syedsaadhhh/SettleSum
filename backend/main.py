"""Run from SettleSum/: uvicorn backend.main:app --host 0.0.0.0 --port 8000."""

import csv
import io
import json
import os
from pathlib import Path
from time import perf_counter_ns
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from .models import ReconcileRequest, Invoice, Deposit
from .reconciliation import reconcile
from .remittance_parser import parse_remittance, extract_text_pdf
from .ledger_exporter import journal_csv, chargeback_csv

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="SettleSum Reconciliation Engine", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def real_telemetry(request: Request, call_next):
    start = perf_counter_ns()
    response = await call_next(request)
    response.headers["X-Request-Time-Ms"] = str((perf_counter_ns() - start) / 1_000_000)
    response.headers["X-Solver-Time-Ms"] = str(
        getattr(request.state, "solve_time_ms", 0)
    )
    response.headers["X-Nodes-Explored"] = str(
        getattr(request.state, "nodes_explored", 0)
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "status": "VALIDATION_ERROR",
            "detail": json.loads(json.dumps(exc.errors(), default=str)),
            "solve_time_ms": 0,
            "nodes_explored": 0,
        },
    )


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "VALIDATION_ERROR" if exc.status_code == 422 else "ERROR",
            "detail": exc.detail,
            "solve_time_ms": 0,
            "nodes_explored": 0,
        },
    )


def run(request, payload):
    result = reconcile(payload)
    request.state.solve_time_ms = result["solve_time_ms"]
    request.state.nodes_explored = result["nodes_explored"]
    return result


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "engine": "multi-state-choice-branch-and-bound",
        "solve_time_ms": 0,
        "nodes_explored": 0,
    }


@app.get("/api/sample-data")
def sample_data():
    invoices = [
        Invoice.model_validate(row).model_dump(mode="json")
        for row in csv.DictReader((ROOT / "sample_data/open_invoices.csv").open())
    ]
    deposits = [
        Deposit.model_validate(row).model_dump(mode="json")
        for row in csv.DictReader((ROOT / "sample_data/bank_deposits.csv").open())
    ]
    return {
        "invoices": invoices,
        "deposits": deposits,
        "remittances": json.loads(
            (ROOT / "sample_data/remittance_notes.json").read_text()
        ),
        "dataset_label": "SYNTHETIC BENCHMARK DATASET",
        "solve_time_ms": 0,
        "nodes_explored": 0,
    }


@app.post("/api/reconcile")
def reconcile_endpoint(payload: ReconcileRequest, request: Request):
    return run(request, payload)


@app.post("/api/parse-remittance")
async def parse_endpoint(request: Request):
    content_type = request.headers.get("content-type", "")
    if int(request.headers.get("content-length", 0)) > 10 * 1024 * 1024:
        raise HTTPException(413, "Remittance exceeds the 10 MB limit")
    document_id, deposit_id = "uploaded-remittance", None
    try:
        if "multipart/form-data" in content_type:
            form = await request.form(max_files=1, max_fields=4)
            file = form.get("file")
            if not file or not hasattr(file, "read"):
                raise ValueError("Upload a PDF or text file using the file field")
            content = await file.read(10 * 1024 * 1024 + 1)
            if len(content) > 10 * 1024 * 1024:
                raise ValueError("Remittance exceeds the 10 MB limit")
            document_id = file.filename or document_id
            deposit_id = form.get("deposit_id") or None
            text = (
                extract_text_pdf(content)
                if content.startswith(b"%PDF")
                else content.decode("utf-8-sig")
            )
        elif "application/json" in content_type:
            data = await request.json()
            text = (
                data
                if isinstance(data, str)
                else data.get("text", data.get("raw_text", ""))
            )
            if isinstance(data, dict):
                document_id, deposit_id = data.get(
                    "document_id", document_id
                ), data.get("deposit_id")
        elif "application/pdf" in content_type:
            text = extract_text_pdf(await request.body())
        else:
            text = (await request.body()).decode("utf-8-sig")
        if len(text) > 100000:
            raise ValueError("Text exceeds 100,000 characters; split the remittance")
        parsed, parser, warning = parse_remittance(text, document_id, deposit_id)
        return {
            **parsed.model_dump(mode="json"),
            "parser": parser,
            "warning": warning,
            "solve_time_ms": 0,
            "nodes_explored": 0,
        }
    except (ValueError, UnicodeError, TypeError, AttributeError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/import-csv")
async def import_csv(request: Request, kind: str):
    if kind not in ("invoices", "deposits"):
        raise HTTPException(422, "kind must be invoices or deposits")
    content = await request.body()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "CSV exceeds 5 MB")
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        rows = list(reader)
        if not rows:
            raise ValueError("CSV is empty; include a header and at least one data row")
        if len(rows) > (2000 if kind == "invoices" else 500):
            raise ValueError("CSV contains too many rows")
        model = Invoice if kind == "invoices" else Deposit
        validated = [model.model_validate(row).model_dump(mode="json") for row in rows]
        key = "invoice_id" if kind == "invoices" else "deposit_id"
        if len({r[key] for r in validated}) != len(validated):
            raise ValueError(f"Duplicate {key}; IDs must be unique")
        return {
            "kind": kind,
            "rows": validated,
            "row_count": len(validated),
            "solve_time_ms": 0,
            "nodes_explored": 0,
        }
    except (ValueError, UnicodeError, csv.Error, ValidationError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/export-journal-csv")
def export_journal(
    payload: ReconcileRequest, request: Request, vendor: str = "quickbooks"
):
    if vendor not in ("quickbooks", "xero"):
        raise HTTPException(422, "vendor must be quickbooks or xero")
    result = run(request, payload)
    return Response(
        journal_csv(result["matches"], vendor),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="settlesum-{vendor}-journal.csv"'
        },
    )


@app.post("/api/export-chargebacks-csv")
def export_chargebacks(
    payload: ReconcileRequest, request: Request, deposit_id: str | None = None
):
    result = run(request, payload)
    matches = result["matches"]
    if deposit_id is not None:
        matches = [m for m in matches if m["deposit_id"] == deposit_id]
        if not matches:
            raise HTTPException(422, "deposit_id was not found in the submitted ledger")
    return Response(
        chargeback_csv(matches),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="settlesum-chargeback-debit-memos.csv"'
        },
    )


# The built React client and Python API share one origin in production.
if (ROOT / "frontend/dist").exists():
    app.mount(
        "/", StaticFiles(directory=ROOT / "frontend/dist", html=True), name="terminal"
    )
