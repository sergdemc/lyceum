import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# cursor_sdk разрешён только в infrastructure, в адаптере саммари.
_OUTSIDE = {
    "aiogram",
    "sqlalchemy",
    "httpx",
    "trafilatura",
    "alembic",
    "apscheduler",
    "cursor_sdk",
}

FORBIDDEN = {
    "domain": _OUTSIDE
    | {
        "lyceum.application",
        "lyceum.infrastructure",
        "lyceum.handlers",
        "lyceum.config",
    },
    "application": _OUTSIDE
    | {
        "lyceum.infrastructure",
        "lyceum.handlers",
        "lyceum.config",
    },
    "handlers": {
        "sqlalchemy",
        "httpx",
        "trafilatura",
        "alembic",
        "cursor_sdk",
        "lyceum.infrastructure",
    },
    "infrastructure": {
        "lyceum.application",
        "lyceum.handlers",
    },
}


def test_imports_point_inward() -> None:
    offenders: list[str] = []
    for layer, banned in FORBIDDEN.items():
        for path in sorted((SRC / "lyceum" / layer).rglob("*.py")):
            for module in _imported_modules(path):
                if any(module == item or module.startswith(item + ".") for item in banned):
                    offenders.append(f"{path.relative_to(ROOT)} -> {module}")
    assert offenders == []


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    package_parts = list(path.relative_to(SRC).parent.parts)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.append(_resolve(package_parts, node))
    return [name for name in found if name]


def _resolve(package_parts: list[str], node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    climb = node.level - 1
    base = package_parts[: len(package_parts) - climb] if climb else list(package_parts)
    if node.module:
        return ".".join([*base, *node.module.split(".")])
    return ".".join(base)
