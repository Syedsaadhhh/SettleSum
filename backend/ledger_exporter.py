"""Balanced GAAP journals and vendor import CSVs. No monetary float arithmetic."""

import csv
import io
from .models import JournalEntryLine

ACCOUNTS = {
    "1010": "Cash - Operating Bank Account",
    "6120": "Bank & Wire Service Charges",
    "4910": "Sales Discounts Taken (Valid)",
    "1215": "AR - Unearned Discount Chargeback",
    "1220": "AR - Short-Pay Dispute Clearing",
    "1200": "Accounts Receivable",
}
STATE_GL = {
    "EARNED_DISCOUNT": "4910",
    "UNEARNED_DISCOUNT": "1215",
    "REMITTANCE_SHORTPAY": "1220",
}


def dollars(cents):
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def money(cents):
    return f"${cents // 100:,}.{cents % 100:02d}"


def make_journal(deposit, solution):
    lines = []

    def add(
        account, debit=0, credit=0, invoice_id=None, document_id=None, description=""
    ):
        lines.append(
            JournalEntryLine(
                gl_account=account,
                account_name=ACCOUNTS[account],
                debit_cents=debit,
                credit_cents=credit,
                invoice_id=invoice_id,
                document_id=document_id,
                description=description,
            ).model_dump()
        )

    add("1010", debit=deposit.amount_cents, description=deposit.bank_reference)
    if solution["wire_fee_cents"]:
        add(
            "6120",
            debit=solution["wire_fee_cents"],
            description="Inferred permitted wire fee",
        )
    memos = []
    for item in solution["invoices"]:
        if item["state"] != "FULL":
            account = STATE_GL[item["state"]]
            add(
                account,
                debit=item["adjustment_cents"],
                invoice_id=item["invoice_id"],
                document_id=item.get("document_id"),
                description=item.get("claim_note", item["state"]),
            )
            if account in ("1215", "1220"):
                memos.append(
                    {
                        "memo_id": f"DM-{deposit.deposit_id}-{item['invoice_id']}",
                        "invoice_id": item["invoice_id"],
                        "amount_cents": item["adjustment_cents"],
                        "reason": item["state"],
                        "gl_account": account,
                        "document_id": item.get("document_id"),
                        "status": "DRAFT_FOR_CONTROLLER_REVIEW",
                    }
                )
        add("1200", credit=item["face_value_cents"], invoice_id=item["invoice_id"])
    debits, credits = sum(x["debit_cents"] for x in lines), sum(
        x["credit_cents"] for x in lines
    )
    if debits != credits:
        raise ValueError("Journal rejected: debit / credit variance")
    return {
        "journal_lines": lines,
        "debits_cents": debits,
        "credits_cents": credits,
        "ledger_variance_cents": debits - credits,
        "ledger_balanced": True,
        "chargeback_memos": memos,
    }


def proof(solution):
    terms = []
    for item in solution["invoices"]:
        label = item["state"].replace("_", " ").title()
        terms.append(
            f"{money(item['face_value_cents'])} [{label}"
            + (
                f": -{money(item['adjustment_cents'])}"
                if item["adjustment_cents"]
                else ""
            )
            + "]"
        )
    if solution["wire_fee_cents"]:
        terms.append(f"-{money(solution['wire_fee_cents'])} [Wire Fee]")
    return (
        " + ".join(terms).replace(" + -", " − ")
        + f" = {money(solution['valuation_cents'] - solution['wire_fee_cents'])}"
    )


def journal_csv(matches, vendor="quickbooks"):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    if vendor == "xero":
        writer.writerow(
            [
                "Narration",
                "Date",
                "Description",
                "AccountCode",
                "TaxRate",
                "Amount",
                "TrackingName1",
                "TrackingOption1",
            ]
        )
    else:
        writer.writerow(
            [
                "Journal No.",
                "Journal Date",
                "Account Name",
                "Debits",
                "Credits",
                "Description",
                "Name",
            ]
        )
    for match in matches:
        for line in match.get("journal_lines", []):
            description = f"{line['gl_account']} | {line['invoice_id'] or match['deposit_id']} | {line['description']}"
            if vendor == "xero":
                writer.writerow(
                    [
                        match["deposit_id"],
                        match["deposit_date"],
                        description,
                        line["gl_account"],
                        "No Tax",
                        dollars(line["debit_cents"] - line["credit_cents"]),
                        "",
                        "",
                    ]
                )
            else:
                writer.writerow(
                    [
                        match["deposit_id"],
                        match["deposit_date"],
                        line["account_name"],
                        dollars(line["debit_cents"]) if line["debit_cents"] else "",
                        dollars(line["credit_cents"]) if line["credit_cents"] else "",
                        description,
                        match["counterparty"]["customer_name"],
                    ]
                )
    return stream.getvalue()


def chargeback_csv(matches):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(
        [
            "Debit Memo",
            "Deposit",
            "Date",
            "Customer",
            "Invoice",
            "Amount",
            "GL Account",
            "Reason",
            "Status",
            "Document",
        ]
    )
    for match in matches:
        for memo in match.get("chargeback_memos", []):
            writer.writerow(
                [
                    memo["memo_id"],
                    match["deposit_id"],
                    match["deposit_date"],
                    match["counterparty"]["customer_name"],
                    memo["invoice_id"],
                    dollars(memo["amount_cents"]),
                    memo["gl_account"],
                    memo["reason"],
                    memo["status"],
                    memo["document_id"] or "",
                ]
            )
    return stream.getvalue()
