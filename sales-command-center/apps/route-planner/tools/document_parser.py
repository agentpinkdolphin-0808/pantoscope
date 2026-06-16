import re

NAME_COLS = re.compile(r"name|practice|provider|office|clinic|company|organization|facility", re.I)
ADDR_COLS = re.compile(r"addr|street|location|address|place", re.I)
CITY_COLS = re.compile(r"^city$", re.I)
STATE_COLS = re.compile(r"^state$|^st$", re.I)
ZIP_COLS = re.compile(r"^zip|^postal", re.I)
WEB_COLS = re.compile(r"web|url|site|link|homepage", re.I)
PHONE_COLS = re.compile(r"phone|tel|fax", re.I)


def parse_document(source: str, doc_type: str) -> list:
    """
    source: file path (csv/excel/pdf) or Google Sheet URL/ID
    doc_type: "csv" | "excel" | "pdf" | "gsheet"
    Returns: [{"name", "address", "website", "phone", ...}, ...]
    """
    if doc_type == "csv":
        return _parse_csv(source)
    elif doc_type == "excel":
        return _parse_excel(source)
    elif doc_type == "pdf":
        return _parse_pdf(source)
    elif doc_type == "gsheet":
        return _parse_gsheet(source)
    else:
        raise ValueError(f"Unknown document type: {doc_type!r}")


def _normalize_columns(df) -> dict:
    """Returns mapping {normalized_name: original_col} for key column types."""
    mapping = {}
    for col in df.columns:
        cs = str(col).strip()
        if "name" not in mapping and NAME_COLS.search(cs):
            mapping["name"] = col
        elif "address" not in mapping and ADDR_COLS.search(cs):
            mapping["address"] = col
        elif "city" not in mapping and CITY_COLS.search(cs):
            mapping["city"] = col
        elif "state" not in mapping and STATE_COLS.search(cs):
            mapping["state"] = col
        elif "zip" not in mapping and ZIP_COLS.search(cs):
            mapping["zip"] = col
        elif "website" not in mapping and WEB_COLS.search(cs):
            mapping["website"] = col
        elif "phone" not in mapping and PHONE_COLS.search(cs):
            mapping["phone"] = col
    return mapping


def _rows_to_entries(df, col_map: dict) -> list:
    entries = []
    for _, row in df.iterrows():
        name = str(row.get(col_map.get("name", ""), "")).strip()
        if not name or name.lower() in ("nan", "none", ""):
            continue

        # Build address: prefer a dedicated address column, else combine city/state/zip
        address = ""
        if "address" in col_map:
            address = str(row.get(col_map["address"], "")).strip()
        if not address or address.lower() in ("nan", "none"):
            parts = []
            for key in ("address", "city", "state", "zip"):
                v = str(row.get(col_map.get(key, ""), "")).strip()
                if v and v.lower() not in ("nan", "none", ""):
                    parts.append(v)
            address = ", ".join(parts)

        # Append city/state if they exist separately and aren't already in address
        if "city" in col_map and "state" in col_map and address:
            city = str(row.get(col_map["city"], "")).strip()
            state = str(row.get(col_map["state"], "")).strip()
            suffix = f"{city}, {state}".strip(", ")
            if suffix and suffix not in address:
                address = f"{address}, {suffix}"

        entry = {
            "name": name,
            "address": address,
            "website": str(row.get(col_map.get("website", ""), "")).strip() or None,
            "phone": str(row.get(col_map.get("phone", ""), "")).strip() or None,
        }
        if entry["website"] and entry["website"].lower() in ("nan", "none"):
            entry["website"] = None
        if entry["phone"] and entry["phone"].lower() in ("nan", "none"):
            entry["phone"] = None

        entries.append(entry)
    return entries


def _parse_csv(path: str) -> list:
    import pandas as pd
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df.columns = [str(c).strip() for c in df.columns]
    col_map = _normalize_columns(df)
    if "name" not in col_map:
        raise ValueError("CSV has no recognizable name column (expected: name, practice, provider, clinic, etc.)")
    return _rows_to_entries(df, col_map)


def _parse_excel(path: str) -> list:
    import pandas as pd
    df = pd.read_excel(path, dtype=str, keep_default_na=False)
    df.columns = [str(c).strip() for c in df.columns]
    col_map = _normalize_columns(df)
    if "name" not in col_map:
        raise ValueError("Excel file has no recognizable name column.")
    return _rows_to_entries(df, col_map)


def _parse_pdf(path: str) -> list:
    import pdfplumber

    entries = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            entries.extend(_extract_entries_from_text(text))
    return entries


def _extract_entries_from_text(text: str) -> list:
    """
    Best-effort extraction from unstructured PDF text.
    Looks for lines that could be business names followed by address-like lines.
    """
    # Common US address pattern: number + street name + optional city/state/zip
    addr_pattern = re.compile(
        r'\d+\s+[A-Z][a-zA-Z\s]+(?:St|Ave|Blvd|Dr|Rd|Ln|Way|Pkwy|Ct|Pl|Suite|Ste|Hwy)[.,]?',
        re.IGNORECASE
    )
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    entries = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if addr_pattern.search(line):
            # This line is an address — try the previous line as the name
            name = lines[i - 1] if i > 0 else ""
            address = line
            if name and len(name) < 80 and not addr_pattern.search(name):
                entries.append({"name": name, "address": address, "website": None, "phone": None})
        i += 1
    return entries


def _parse_gsheet(sheet_url: str) -> list:
    import gspread
    from pathlib import Path

    creds_path = Path(__file__).parent.parent / "credentials.json"
    token_path = Path(__file__).parent.parent / "token.json"

    if creds_path.exists():
        gc = gspread.oauth(
            credentials_filename=str(creds_path),
            authorized_user_filename=str(token_path),
        )
    else:
        raise RuntimeError(
            "credentials.json not found. Set up Google OAuth to use Google Sheets. "
            "See: https://docs.gspread.org/en/latest/oauth2.html"
        )

    sh = gc.open_by_url(sheet_url)
    worksheet = sh.get_worksheet(0)
    rows = worksheet.get_all_records()

    import pandas as pd
    df = pd.DataFrame(rows, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    col_map = _normalize_columns(df)
    if "name" not in col_map:
        raise ValueError("Google Sheet has no recognizable name column.")
    return _rows_to_entries(df, col_map)
