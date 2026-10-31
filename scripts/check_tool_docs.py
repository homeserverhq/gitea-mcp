#!/usr/bin/env python3
"""Validate Gitea MCP tool signatures and docstrings."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "src" / "main.py"
DATE_PHRASE = "ISO 8601 format (2026-06-22T15:00:00-04:00)."
DATE_NAMES = {"since", "before", "until", "due_date", "due_on", "last_read_at", "created", "date"}
DATE_EXCEPTIONS = {("issue_search_issues", "created")}
INCLUDE_DOC = "Default False (common fields only). Set True for all fields."
SUDO_PREFIX = "Admin-only username to impersonate"
PRIMITIVE = {"str", "int", "float", "bool"}
PROHIBITED = ("Optional[", "Any", "dict[", "Dict[", "Union[", "tuple[", "set[", "frozenset[")


def annotation(node: ast.AST | None) -> str:
    return ast.unparse(node) if node is not None else ""


def is_primitive_list(ann: str) -> bool:
    ann = ann.replace(" | None", "").strip()
    if re.fullmatch(r"list\[(str|int|float|bool)\]", ann):
        return True
    if re.fullmatch(r"list\[Literal\[[^\]]+\]\]", ann):
        return True
    return False


def literal_values(ann: str) -> list[str]:
    return re.findall(r"'([^']+)'", ann)


def main() -> int:
    tree = ast.parse(MAIN.read_text())
    tools = [
        n for n in ast.walk(tree)
        if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef))
        and any(ast.unparse(d).startswith("mcp.tool") for d in n.decorator_list)
    ]
    errors: list[str] = []

    for func in tools:
        doc = ast.get_docstring(func) or ""
        params = [a.arg for a in func.args.args if a.arg != "ctx"]
        if not doc:
            errors.append(f"{func.name}: missing docstring")
            continue
        if "\n\nArgs:\n" not in doc:
            errors.append(f"{func.name}: missing blank line before Args:")
        if "ctx:" in doc:
            errors.append(f"{func.name}: ctx must not be documented")
        if "(optional)" in doc.lower() or "(required)" in doc.lower():
            errors.append(f"{func.name}: remove (optional)/(required) text")
        first = doc.strip().splitlines()[0]
        if not first.endswith("."):
            errors.append(f"{func.name}: function description must end with a period")

        docs: dict[str, str] = {}
        for line in doc.splitlines():
            m = re.match(r"\s+([A-Za-z_][A-Za-z0-9_]*):\s*(.*)", line)
            if m:
                docs[m.group(1)] = m.group(2).strip()

        for name in params:
            if name not in docs:
                errors.append(f"{func.name}.{name}: missing docstring parameter")
                continue
            desc = docs[name]
            if name == "include_all_fields":
                if desc != INCLUDE_DOC:
                    errors.append(f"{func.name}.{name}: include_all_fields wording mismatch")
            elif name == "sudo":
                if not desc.startswith(SUDO_PREFIX):
                    errors.append(f"{func.name}.{name}: sudo wording mismatch")
            elif not desc.endswith("."):
                errors.append(f"{func.name}.{name}: description must end with a period")

            ann = annotation(next(a.annotation for a in func.args.args if a.arg == name))
            for bad in PROHIBITED:
                if bad in ann:
                    errors.append(f"{func.name}.{name}: prohibited annotation {ann}")
            if ann.startswith("list[") and not is_primitive_list(ann):
                errors.append(f"{func.name}.{name}: list element must be a primitive ({ann})")
            if "*" in ann:
                pass

            original = name
            is_date = original in DATE_NAMES and (func.name, original) not in DATE_EXCEPTIONS
            if is_date and desc != DATE_PHRASE:
                errors.append(f"{func.name}.{name}: datetime wording mismatch")
            if ann == "bool" and name != "include_all_fields" and "true or false" not in desc.lower():
                errors.append(f"{func.name}.{name}: boolean must document true or false")
            values = literal_values(ann)
            if values:
                missing = [v for v in values if v not in desc]
                if missing:
                    errors.append(f"{func.name}.{name}: missing enum values {missing}")

    # Pydantic model fields
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(isinstance(b, ast.Name) and b.id == "BaseModel" for b in node.bases):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
                continue
            desc = ""
            if isinstance(stmt.value, ast.Call):
                for kw in stmt.value.keywords:
                    if kw.arg == "description" and isinstance(kw.value, ast.Constant):
                        desc = str(kw.value.value)
            if not desc:
                errors.append(f"{node.name}.{stmt.target.id}: missing Field description")

    if errors:
        print(f"FAILED: {len(errors)} issue(s)")
        for err in errors:
            print(f" - {err}")
        return 1

    print(f"PASS: {len(tools)} tools validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
