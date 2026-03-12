"""
apply_rq_patch.py
=================
Standalone script that applies android_rq_patch.json to fix the
`rationally_qualified` field for all Android devices in compatibility.json.

This is the belt-and-suspenders fallback: run it after parse_pdf.py as a
post-processing step to guarantee correct RQ values even if the PDF parser
has trouble with a future revision.

Usage:
    python scripts/apply_rq_patch.py \
        data/compatibility.json \
        scripts/android_rq_patch.json

Or with defaults (no args needed if paths match):
    python scripts/apply_rq_patch.py
"""

import json
import re
import sys
import os

DEFAULT_DATA_PATH  = "data/compatibility.json"
DEFAULT_PATCH_PATH = os.path.join(os.path.dirname(__file__), "android_rq_patch.json")


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def clean_name(raw: str) -> str:
    """Strip trailing Yes/No RQ token from a device name."""
    cleaned = re.sub(r"\s+(Yes|No\s*\([^)]*\)|No)\s*$", "", raw, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", cleaned).strip().lower()


def apply_patch(data_path: str, patch_path: str) -> None:
    if not os.path.exists(data_path):
        print(f"ERROR: data file not found: {data_path}")
        sys.exit(1)
    if not os.path.exists(patch_path):
        print(f"ERROR: patch file not found: {patch_path}")
        sys.exit(1)

    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)
    with open(patch_path, encoding="utf-8") as f:
        patch = json.load(f)

    products = data.get("products", {})
    total_patched = 0
    total_unmatched = 0

    for prod_name in ("E3", "365", "NOW"):
        prod_patch = patch.get(prod_name, {})
        android_devices = products.get(prod_name, {}).get("android", [])

        patched = 0
        unmatched = 0

        for device in android_devices:
            mfr = normalize(device.get("manufacturer", ""))
            model_key = clean_name(device.get("name", ""))

            mfr_patch = prod_patch.get(mfr, {})

            if model_key in mfr_patch:
                old_val = device["rationally_qualified"]
                new_val = mfr_patch[model_key]
                device["rationally_qualified"] = new_val
                if old_val != new_val:
                    patched += 1
            else:
                # Try partial match: find the longest patch key that is a
                # substring of model_key or vice versa
                best_key = None
                best_len = 0
                for pk in mfr_patch:
                    if pk in model_key or model_key in pk:
                        if len(pk) > best_len:
                            best_key = pk
                            best_len = len(pk)

                if best_key:
                    old_val = device["rationally_qualified"]
                    new_val = mfr_patch[best_key]
                    device["rationally_qualified"] = new_val
                    if old_val != new_val:
                        patched += 1
                else:
                    unmatched += 1
                    print(f"  ⚠ No patch match: {prod_name} / {mfr} / '{model_key}'")

        total_patched += patched
        total_unmatched += unmatched
        rq_count = sum(1 for d in android_devices if d["rationally_qualified"])
        print(f"   {prod_name} Android: {len(android_devices)} devices, "
              f"{patched} values corrected, {rq_count} now RQ=true, "
              f"{unmatched} unmatched")

    # Write back
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Patch applied → {data_path}")
    print(f"   {total_patched} RQ values corrected, {total_unmatched} unmatched entries")

    if total_unmatched > 0:
        print("   ℹ  Unmatched entries keep their original value (false if parser bug persists).")


if __name__ == "__main__":
    data_path  = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DATA_PATH
    patch_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PATCH_PATH
    apply_patch(data_path, patch_path)
