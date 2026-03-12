"""
parse_pdf.py  —  Senseonics Compatibility PDF Parser
=====================================================
Parses all 6 tables from the Senseonics handheld-device compatibility PDF
(3 products × 2 platforms) and writes data/compatibility.json.

Usage:
    python scripts/parse_pdf.py pdf/compatibility.pdf

Column structure in the PDF tables
-----------------------------------
iOS tables    (3 cols visible after manufacturer):
    Device Name | Model Number | OS Version | Rationally Qualified

Android tables (3 cols visible after manufacturer):
    Device Name | Model Number | OS Version | Rationally Qualified

The parser uses pdfplumber for accurate table detection.  If a cell in
the "Rationally Qualified" column contains "Yes" (case-insensitive) the
flag is set to true; anything else (including "No", blank, or a
model-number exclusion note like "No (XQ-BE62)") is false.

Key fix vs. the previous parser
---------------------------------
The old parser concatenated the RQ Yes/No token into the model-name cell
for Android tables and then set every android `rationally_qualified` to
false.  This version explicitly identifies the last column as the RQ
column regardless of table position and strips any stray tokens from the
name field.
"""

import json
import re
import sys
import os
from pathlib import Path
from datetime import date

try:
    import pdfplumber
except ImportError:
    print("ERROR: pdfplumber not installed. Run: pip install pdfplumber --break-system-packages")
    sys.exit(1)

# ── Product / section markers ─────────────────────────────────────────────────
# These strings appear as headings in the PDF immediately before each table.
PRODUCT_MARKERS = {
    "E3":  ["eversense e3",  "e3 system"],
    "365": ["eversense 365", "365 system"],
    "NOW": ["eversense now", "now system"],
}

PLATFORM_MARKERS = {
    "android": ["android"],
    "ios":     ["ios", "apple"],
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    """Lowercase, collapse whitespace."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def is_rq(cell: str) -> bool:
    """Return True if the cell value unambiguously means 'Yes' for RQ."""
    v = normalize(cell)
    return v == "yes" or v.startswith("yes ")


def clean_name(raw: str) -> str:
    """
    Strip the RQ Yes/No token that the old parser left in the name field.
    e.g. "Google Pixel 6 Pixel 6 Yes"  →  "Google Pixel 6"
         "Nokia G300 N1374DL Yes"       →  "Nokia G300"     (model# handled separately)
         "Samsung Galaxy S22 SM-S901... Yes" → "Samsung Galaxy S22"
    """
    # Remove trailing " Yes" / " No" / " No (...)"
    cleaned = re.sub(r"\s+(Yes|No\s*\([^)]*\)|No)\s*$", "", raw, flags=re.IGNORECASE)
    # Collapse multiple spaces
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def extract_rq_from_name(raw: str) -> bool | None:
    """
    If the RQ token was embedded in the name, extract and return it.
    Returns True/False/None (None = not found in name).
    """
    m = re.search(r"\b(Yes|No\s*(?:\([^)]*\))?)\s*$", raw, re.IGNORECASE)
    if m:
        return m.group(1).strip().lower() == "yes"
    return None


# ── Table-row parser ──────────────────────────────────────────────────────────

def parse_row(row: list[str | None], has_rq_col: bool) -> dict | None:
    """
    Convert a raw table row into a device dict.

    Expected column order (after stripping empty leading cells):
        0: Manufacturer (may be blank — carry forward from previous row)
        1: Device Name
        2: Model Number  (may be blank)
        3: OS Version    (may be blank)
        4: Rationally Qualified  (Yes / No / No (model))

    Some rows omit the manufacturer column so everything shifts left by 1.
    We detect this by checking whether the first cell looks like a
    manufacturer name vs. a device name.
    """
    # Normalise cells
    cells = [c.strip() if c else "" for c in row]
    # Drop fully-empty rows
    if all(c == "" for c in cells):
        return None

    # We expect 4 or 5 non-empty-header columns.
    # Compact to only non-None:
    non_empty = [c for c in cells if c != ""]
    if len(non_empty) < 2:
        return None

    # If the last cell is clearly a RQ value, separate it
    rq_val = None
    if has_rq_col and cells:
        last = cells[-1] if cells else ""
        if re.match(r"^(Yes|No(\s*\([^)]+\))?)$", last.strip(), re.IGNORECASE):
            rq_val = last.strip().lower() == "yes"
            cells = cells[:-1]

    # Now cells should be: [manufacturer?], name, model_number?, os_version?
    # Heuristic: if we have ≥4 remaining cells the first is manufacturer
    manufacturer = ""
    if len(cells) >= 4:
        manufacturer = cells[0]
        name_raw = cells[1]
        model_number = cells[2]
        os_version = cells[3]
    elif len(cells) == 3:
        name_raw = cells[0]
        model_number = cells[1]
        os_version = cells[2]
    elif len(cells) == 2:
        name_raw = cells[0]
        model_number = ""
        os_version = cells[1]
    else:
        name_raw = cells[0]
        model_number = ""
        os_version = ""

    # If RQ wasn't found as a clean last-cell, try extracting from name
    if rq_val is None:
        rq_from_name = extract_rq_from_name(name_raw)
        if rq_from_name is not None:
            rq_val = rq_from_name

    name = clean_name(name_raw)

    # Skip header rows or junk
    lowname = name.lower()
    if any(kw in lowname for kw in ["device name", "model name", "handset", "compatible devices"]):
        return None

    return {
        "manufacturer": manufacturer,
        "name": name,
        "model_number": model_number,
        "os_version": os_version,
        "rationally_qualified": bool(rq_val),
    }


# ── Section detection ─────────────────────────────────────────────────────────

def detect_section(text: str) -> tuple[str | None, str | None]:
    """
    Given a block of text from a page, return (product, platform) if both
    markers are found, else (None, None).
    """
    low = normalize(text)
    product = None
    for prod, markers in PRODUCT_MARKERS.items():
        if any(m in low for m in markers):
            product = prod
            break

    platform = None
    for plat, markers in PLATFORM_MARKERS.items():
        if any(m in low for m in markers):
            platform = plat
            break

    return product, platform


# ── Core parser ───────────────────────────────────────────────────────────────

def parse_pdf(pdf_path: str) -> dict:
    output = {
        "last_updated": date.today().isoformat(),
        "revision": "50",
        "products": {
            "E3":  {"ios": [], "android": []},
            "365": {"ios": [], "android": []},
            "NOW": {"ios": [], "android": []},
        }
    }

    current_product = None
    current_platform = None

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text() or ""

            # Try to detect product/platform from page text
            prod, plat = detect_section(page_text)
            if prod:
                current_product = prod
            if plat:
                current_platform = plat

            # Extract tables from this page
            tables = page.extract_tables()
            if not tables:
                continue

            for table in tables:
                if not table:
                    continue

                # Check if this table has a Rationally Qualified column header
                header_row = table[0] if table else []
                header_cells = [normalize(c or "") for c in header_row]
                has_rq_col = any("rational" in h or "qualified" in h for h in header_cells)

                # Also try to detect product/platform from the header row text
                header_text = " ".join(c or "" for c in header_row)
                hp, hpl = detect_section(header_text)
                if hp:
                    current_product = hp
                if hpl:
                    current_platform = hpl

                if current_product is None or current_platform is None:
                    # Try harder — look at all cell text on this table
                    all_text = " ".join(
                        c or "" for row in table for c in (row or [])
                    )
                    ap, apl = detect_section(all_text)
                    if ap:
                        current_product = ap
                    if apl:
                        current_platform = apl

                if current_product is None or current_platform is None:
                    continue

                # Determine if the "Rationally Qualified" column exists by
                # also checking common alternative: last column is Yes/No
                # for most rows (sample first 5 data rows)
                if not has_rq_col:
                    sample_last = []
                    for row in table[1:6]:
                        if row:
                            last = normalize(row[-1] or "")
                            sample_last.append(last)
                    yes_no_count = sum(
                        1 for v in sample_last
                        if re.match(r"^(yes|no(\s*\([^)]+\))?)$", v)
                    )
                    if yes_no_count >= 2:
                        has_rq_col = True

                last_manufacturer = ""
                for row in table[1:]:  # skip header
                    if not row:
                        continue

                    # Carry forward manufacturer from previous row if blank
                    if row[0] and row[0].strip():
                        last_manufacturer = row[0].strip()
                    elif row[0] is None or row[0].strip() == "":
                        row = [last_manufacturer] + list(row[1:])

                    device = parse_row(list(row), has_rq_col)
                    if device is None:
                        continue
                    if not device["name"]:
                        continue

                    # Fill manufacturer from carry-forward if blank
                    if not device["manufacturer"] and last_manufacturer:
                        device["manufacturer"] = last_manufacturer
                    elif device["manufacturer"]:
                        last_manufacturer = device["manufacturer"]

                    output["products"][current_product][current_platform].append(device)

    return output


# ── Deduplication ─────────────────────────────────────────────────────────────

def dedup(devices: list[dict]) -> list[dict]:
    """Remove exact-duplicate entries (same name + model_number)."""
    seen = set()
    result = []
    for d in devices:
        key = (normalize(d["name"]), normalize(d.get("model_number", "")))
        if key not in seen:
            seen.add(key)
            result.append(d)
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/parse_pdf.py pdf/compatibility.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"ERROR: PDF not found at {pdf_path}")
        sys.exit(1)

    print(f"📄 Parsing {pdf_path}...")
    data = parse_pdf(pdf_path)

    # Dedup
    for product in data["products"].values():
        for platform in ("ios", "android"):
            product[platform] = dedup(product[platform])

    # Write output
    os.makedirs("data", exist_ok=True)
    out_path = "data/compatibility.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Summary
    total = 0
    rq_total = 0
    for prod_name, prod_data in data["products"].items():
        ios_count = len(prod_data["ios"])
        android_count = len(prod_data["android"])
        ios_rq = sum(1 for d in prod_data["ios"] if d["rationally_qualified"])
        android_rq = sum(1 for d in prod_data["android"] if d["rationally_qualified"])
        total += ios_count + android_count
        rq_total += ios_rq + android_rq
        print(f"   {prod_name}: iOS={ios_count} (RQ={ios_rq})  Android={android_count} (RQ={android_rq})")

    print(f"\n✅ Wrote {out_path}")
    print(f"📊 Total devices: {total}  (RQ: {rq_total})")

    if total == 0:
        print("⚠️  WARNING: No devices parsed — check PDF structure")
        sys.exit(1)

    # Sanity check: if android RQ count is 0 for any product, warn loudly
    for prod_name, prod_data in data["products"].items():
        android_rq = sum(1 for d in prod_data["android"] if d["rationally_qualified"])
        android_count = len(prod_data["android"])
        if android_count > 0 and android_rq == 0:
            print(f"⚠️  WARNING: {prod_name} Android has {android_count} devices but 0 RQ=true — possible parsing bug!")


if __name__ == "__main__":
    main()
