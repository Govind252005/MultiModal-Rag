from pathlib import Path
import re

ROOT = Path("backend")

# Local top-level modules/packages inside backend/
TOP_LEVEL = {
    "auth",
    "cache",
    "config",
    "diagnose_gemini",
    "generation",
    "ingestion",
    "keystore",
    "launcher",
    "logging_utils",
    "main",
    "observability",
    "retrieval",
    "sessions",
    "verify_backend",
}

changed_files = []
changes = []

def fix_line(line, path):
    original = line

    # ---------------------------------------------------------
    # import config
    # import auth
    # import generation.answer
    # import keystore
    # ---------------------------------------------------------
    match = re.match(
        r'^(\s*)import\s+([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)(.*)$',
        line
    )

    if match:
        indent, module, rest = match.groups()

        root = module.split(".")[0]

        if root in TOP_LEVEL and not module.startswith("backend."):
            line = f"{indent}import backend.{module}{rest}\n" \
                if line.endswith("\n") else \
                f"{indent}import backend.{module}{rest}"

    # ---------------------------------------------------------
    # from config import ...
    # from generation import ...
    # from generation.providers import ...
    # from retrieval import ...
    # ---------------------------------------------------------
    match = re.match(
        r'^(\s*)from\s+([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s+import\s+(.+)$',
        line
    )

    if match:
        indent, module, imported = match.groups()

        root = module.split(".")[0]

        if (
            root in TOP_LEVEL
            and not module.startswith("backend.")
        ):
            line = (
                f"{indent}from backend.{module} import {imported}"
            )

    if line != original:
        changes.append(
            f"{path}: {original.strip()}  ->  {line.strip()}"
        )

    return line


for path in ROOT.rglob("*.py"):
    # Never touch virtual environments or generated files
    if ".venv" in path.parts:
        continue

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    new_lines = [
        fix_line(line, path)
        for line in lines
    ]

    new_text = "".join(new_lines)

    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        changed_files.append(path)


print()
print("=" * 80)
print("BACKEND IMPORT CLEANUP")
print("=" * 80)

print(f"\nFiles changed: {len(changed_files)}")

for path in changed_files:
    print(f"  [CHANGED] {path}")

print("\nImport changes:")
print("-" * 80)

for change in changes:
    print(change)

print("\n" + "=" * 80)
print("DONE")
print("=" * 80)

