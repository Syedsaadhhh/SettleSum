"""Reproducible structural red-flag checks over application source, not fixtures."""

import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_NAMES = re.compile(
    r"\b(?:Apex|Vanguard|Kestrel|Northstar|Meridian|Solstice)\b", re.I
)
SAMPLE_ID = re.compile(r"\b(?:DEP|INV|CUST)-[A-Z0-9-]*\d[A-Z0-9-]*\b", re.I)
DELAY = re.compile(r"\b(?:time\.sleep|asyncio\.sleep|setTimeout|setInterval)\s*\(")


def audit():
    files = sorted(
        p
        for folder in ("api", "backend", "frontend")
        for p in (ROOT / folder).rglob("*")
        if p.is_file()
        and p.suffix in {".py", ".js", ".jsx", ".mjs", ".css", ".html", ".svg"}
        and not any(
            part in {"node_modules", "dist", "__pycache__", "test", "tests"}
            for part in p.parts
        )
        and not p.name.startswith(("test_", "seed"))
    )
    failures = []
    for path in files:
        source = path.read_text()
        for label, pattern in [
            ("sample customer literal", SAMPLE_NAMES),
            ("sample-like concrete identifier", SAMPLE_ID),
            ("artificial delay", DELAY),
        ]:
            for hit in pattern.finditer(source):
                failures.append(
                    f"{path.relative_to(ROOT)}:{source.count(chr(10), 0, hit.start()) + 1}: {label}: {hit[0]}"
                )
        if path.suffix == ".py":
            ast.parse(source)
        if path.suffix == ".css" and re.search(
            r"(?:linear|radial|conic)-gradient\s*\(", source
        ):
            failures.append(f"{path.relative_to(ROOT)}: decorative gradient")
    for name in ("solver.py", "ledger_exporter.py"):
        tree = ast.parse((ROOT / "backend" / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                failures.append(
                    f"backend/{name}:{node.lineno}: floating-point literal in monetary module"
                )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "float"
            ):
                failures.append(
                    f"backend/{name}:{node.lineno}: monetary float conversion"
                )
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                # Only wall-clock nanoseconds -> milliseconds may use true division.
                if (
                    name != "solver.py"
                    or ast.unparse(node.left) != "perf_counter_ns() - started"
                    or ast.literal_eval(node.right) != 1_000_000
                ):
                    failures.append(
                        f"backend/{name}:{node.lineno}: true division outside telemetry"
                    )
    tree = ast.parse((ROOT / "backend/solver.py").read_text())
    visit = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "visit"
    )
    counter = any(
        isinstance(n, ast.AugAssign)
        and isinstance(n.target, ast.Name)
        and n.target.id == "nodes"
        and isinstance(n.op, ast.Add)
        and isinstance(n.value, ast.Constant)
        and n.value.value == 1
        for n in ast.walk(visit)
    )
    if not counter:
        failures.append("solver search recursion has no actual node increment")
    requirements = (ROOT / "backend/requirements.txt").read_text().lower()
    if any(name in requirements for name in ("dpss", "subset-sum", "ortools")):
        failures.append("external optimization wrapper")
    return {
        "status": "PASS" if not failures else "FAIL",
        "source_files_scanned": len(files),
        "scope": [str(p.relative_to(ROOT)) for p in files],
        "failures": failures,
        "checks": [
            "No sample names or concrete fixture IDs in app source",
            "No fake latency calls",
            "No floating monetary literals/conversions/true division in solver/exporter",
            "Real recursive node counter and measured wall time",
            "No external solver package",
            "No CSS gradients",
        ],
    }


if __name__ == "__main__":
    report = audit()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["status"] == "PASS" else 1)
