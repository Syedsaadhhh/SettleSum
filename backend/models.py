"""Validated external schemas. Money enters as cents and stays integer thereafter."""

from datetime import date
from decimal import Decimal
from typing import Literal
import math
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_CENTS = 2**63 - 1


def to_cents(value) -> int:
    # Required currency ingress convention. Financial arithmetic never uses float.
    number = float(str(value).replace(",", "").replace("$", ""))
    if not math.isfinite(number):
        raise ValueError("Amount must be finite")
    cents = int(round(number * 100))
    if abs(cents) > MAX_CENTS:
        raise ValueError("Amount exceeds signed 64-bit cents")
    return cents


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Money(Schema):
    amount_cents: int = Field(gt=0, le=MAX_CENTS, strict=True)

    @model_validator(mode="before")
    @classmethod
    def normalize_money(cls, values):
        values = dict(values)
        if "amount" in values:
            amount = values.pop("amount")
            if "amount_cents" not in values or values["amount_cents"] in ("", None):
                values["amount_cents"] = to_cents(amount)
        if isinstance(values.get("amount_cents"), str):
            values["amount_cents"] = int(values["amount_cents"])
        return values


class Invoice(Money):
    invoice_id: str = Field(min_length=1, max_length=100)
    customer_id: str = Field(min_length=1, max_length=100)
    customer_name: str = Field(min_length=1, max_length=200)
    invoice_date: date
    due_date: date
    discount_terms: str = "Net 30"
    discount_pct: Decimal = Field(
        default=Decimal("0"), ge=0, lt=1, max_digits=8, decimal_places=6
    )
    discount_days: int = Field(default=0, ge=0, le=365)

    @model_validator(mode="before")
    @classmethod
    def parse_terms(cls, values):
        values = dict(values)
        term = re.search(
            r"(\d+(?:\.\d+)?)\s*/\s*(\d+)", values.get("discount_terms", "")
        )
        if term:
            if values.get("discount_pct") in (None, ""):
                values["discount_pct"] = Decimal(term[1]) / 100
            if values.get("discount_days") in (None, ""):
                values["discount_days"] = int(term[2])
        return values

    @model_validator(mode="after")
    def validate_dates(self):
        if self.due_date < self.invoice_date:
            raise ValueError("due_date cannot precede invoice_date")
        return self


class Deposit(Money):
    deposit_id: str = Field(min_length=1, max_length=100)
    deposit_date: date
    raw_payer_memo: str = Field(min_length=1, max_length=2000)
    bank_reference: str = ""


class RemittanceReference(Schema):
    invoice_id: str = Field(min_length=1, max_length=100)
    paid_amount_cents: int | None = Field(default=None, ge=0, le=MAX_CENTS, strict=True)
    deduction_cents: int = Field(default=0, ge=0, le=MAX_CENTS, strict=True)
    reason_code: str = "DOCUMENTED_CLAIM"
    note: str = ""


class Remittance(Schema):
    document_id: str = "uploaded-remittance"
    deposit_id: str | None = None
    customer_name: str = ""
    raw_text: str = ""
    referenced_invoices: list[RemittanceReference] = Field(default_factory=list)


class SolverConfig(Schema):
    allow_wire_fees: bool = True
    wire_fee_options_cents: list[int] = Field(
        default_factory=lambda: [0, 1000, 1500, 2000, 2500, 3000], max_length=100
    )
    wire_fee_band_min_cents: int | None = Field(default=None, ge=0, le=10000000)
    wire_fee_band_max_cents: int | None = Field(default=None, ge=0, le=10000000)
    allow_discounts: bool = True
    max_subset_size: int = Field(default=6, ge=1, le=20)
    max_nodes: int = Field(default=2000000, ge=1, le=10000000)
    entity_match_threshold: float = Field(default=0.65, ge=0.5, le=1)

    @field_validator("wire_fee_options_cents")
    @classmethod
    def validate_fees(cls, values):
        if any(type(x) is not int or x < 0 or x > 10000000 for x in values):
            raise ValueError(
                "Wire fees must be nonnegative integer cents, at most $100,000"
            )
        return sorted(set([0, *values]))

    @model_validator(mode="after")
    def validate_band(self):
        lo, hi = self.wire_fee_band_min_cents, self.wire_fee_band_max_cents
        if (lo is None) != (hi is None) or (lo is not None and lo > hi):
            raise ValueError("Provide both wire fee bounds, with minimum <= maximum")
        return self


class ReconcileRequest(Schema):
    invoices: list[Invoice] = Field(min_length=1, max_length=2000)
    deposits: list[Deposit] = Field(min_length=1, max_length=500)
    remittances: list[Remittance] = Field(default_factory=list, max_length=1000)
    config: SolverConfig = Field(default_factory=SolverConfig)

    @model_validator(mode="after")
    def unique_ids(self):
        for field, key in [("invoices", "invoice_id"), ("deposits", "deposit_id")]:
            records = getattr(self, field)
            if len({getattr(x, key) for x in records}) != len(records):
                raise ValueError(f"Duplicate {key}; IDs must be unique")
            if sum(x.amount_cents for x in records) > MAX_CENTS:
                raise ValueError(f"{field} total exceeds signed 64-bit cents")
        customers = {}
        for invoice in self.invoices:
            if (
                invoice.customer_id in customers
                and customers[invoice.customer_id] != invoice.customer_name
            ):
                raise ValueError(
                    "Each customer_id must have one consistent customer_name"
                )
            customers[invoice.customer_id] = invoice.customer_name
        return self


class JournalEntryLine(Schema):
    gl_account: str
    account_name: str
    debit_cents: int = Field(default=0, ge=0, le=MAX_CENTS)
    credit_cents: int = Field(default=0, ge=0, le=MAX_CENTS)
    invoice_id: str | None = None
    document_id: str | None = None
    description: str = ""

    @model_validator(mode="after")
    def one_side(self):
        if (self.debit_cents > 0) == (self.credit_cents > 0):
            raise ValueError("A journal line must have exactly one positive side")
        return self
