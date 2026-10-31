#!/usr/bin/env python3
"""Validate Gitea MCP tool signatures and docstrings."""

from __future__ import annotations

import ast
import collections
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "src" / "main.py"
sys.path.insert(0, str(ROOT))
from src.client import TOOL_SPECS
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
    groups = {"basic", "primary", "advanced"}
    service = "gitea"
    destructive_exceptions = {"issue_unlock_issue", "repo_cancel_scheduled_auto_merge"}
    group_counts: collections.Counter[str] = collections.Counter()
    summaries: dict[str, list[str]] = collections.defaultdict(list)

    for func in tools:
        decorators = [
            d for d in func.decorator_list
            if isinstance(d, ast.Call)
            and isinstance(d.func, ast.Attribute)
            and d.func.attr == "tool"
        ]
        if len(decorators) != 1:
            errors.append(f"{func.name}: expected exactly one mcp.tool decorator")
            continue
        dec = decorators[0]
        kwargs = {k.arg: k.value for k in dec.keywords}
        if set(kwargs) != {"tags", "annotations"}:
            errors.append(f"{func.name}: decorator must contain only tags and annotations")
        try:
            tag_values = set(ast.literal_eval(kwargs["tags"]))
        except Exception:
            tag_values = set()
        if len(tag_values) != 2:
            errors.append(f"{func.name}: expected exactly two tags, got {sorted(tag_values)}")
        if service not in tag_values:
            errors.append(f"{func.name}: missing service tag {service}")
        if len(tag_values & groups) != 1:
            errors.append(f"{func.name}: expected exactly one group tag, got {sorted(tag_values & groups)}")
        else:
            group_counts[next(iter(tag_values & groups))] += 1
        ann = kwargs.get("annotations")
        if not isinstance(ann, ast.Call):
            errors.append(f"{func.name}: missing ToolAnnotations")
        else:
            ak = {k.arg: k.value for k in ann.keywords}
            expected_title = func.name.replace("_", " ").title()
            title = ak.get("title")
            if not isinstance(title, ast.Constant) or title.value != expected_title:
                errors.append(f"{func.name}: title must be {expected_title!r}")
            method = TOOL_SPECS.get(func.name, {}).get("method", "PUT")
            expected = {
                "readOnlyHint": method == "GET",
                "destructiveHint": method == "DELETE" and func.name not in destructive_exceptions,
                "idempotentHint": method != "POST",
                "openWorldHint": func.name == "repo_migrate",
            }
            for key, want in expected.items():
                node = ak.get(key)
                if not isinstance(node, ast.Constant) or bool(node.value) != want:
                    errors.append(f"{func.name}: {key} must be {want}")

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
        summaries[first].append(func.name)
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

    for summary, names in summaries.items():
        if len(names) > 1:
            errors.append(f"duplicate tool description {summary!r}: {', '.join(names)}")

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

    print(
        f"PASS: {len(tools)} tools validated; "
        f"basic={group_counts['basic']}, primary={group_counts['primary']}, advanced={group_counts['advanced']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
