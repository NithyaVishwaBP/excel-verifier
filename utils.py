"""Shared types and helpers for the BOM verification tool."""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class ErrorRow:
    Sheet: str
    Row: int
    Type: str
    Expected: str
    Found: str
    Message: str


@dataclass
class VerifyResult:
    rm_checked: int = 0
    sfg_mismatches: int = 0
    sku_checked: int = 0
    formula_errors: int = 0
    errors: list = field(default_factory=list)
    corrected_bytes: Optional[bytes] = None
    audit_bytes: Optional[bytes] = None

    def add(self, sheet, row, etype, expected, found, message):
        self.errors.append(ErrorRow(sheet, row, etype, str(expected), str(found), message))


ALLERGENS = [
    "Gluten", "Milk", "Egg", "Fish", "Soy", "Peanut", "Celery",
    "Mustard", "Sesame", "Sulphite", "Lupin", "Mollusc",
    "Crustacean", "Nuts",
]


def find_sheet_by_keyword(sheet_names, keyword):
    """Find the first sheet name containing the keyword (case-insensitive)."""
    for name in sheet_names:
        if keyword.lower() in name.lower():
            return name
    return None


def find_column(df_columns, keywords):
    """Find the first column matching any of the keywords (case-insensitive substring)."""
    cols = list(df_columns)
    lowered = [str(c).lower() for c in cols]
    for kw in keywords:
        kw_l = kw.lower()
        for i, c in enumerate(lowered):
            if kw_l in c:
                return cols[i]
    return None


def to_int(value):
    """Coerce a value to int (1/0), returning 0 for blanks/NaN/None."""
    if value is None:
        return 0
    try:
        if isinstance(value, float):
            if value != value:  # NaN
                return 0
            return int(value)
        s = str(value).strip().lower()
        if s in ("", "nan", "none", "false"):
            return 0
        if s in ("1", "true", "yes", "y", "t"):
            return 1
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def safe_str(value):
    if value is None:
        return ""
    try:
        f = float(value)
        if f != f:
            return ""
        if f == int(f):
            return str(int(f))
        return str(f)
    except (ValueError, TypeError):
        return str(value).strip()
