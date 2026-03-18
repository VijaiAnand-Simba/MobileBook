#!/usr/bin/env python3
"""
Parse compatibility documents - supports both DOCX and PDF
Tries DOCX first, falls back to PDF
"""

import json
import os
import sys
from datetime import datetime

# Try to import DOCX extractor
try:
    from word_extractor import parse_compatibility_docx
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False
    print("⚠️  python-docx not available, will use PDF fallback")

# Try to import PDF extractor
try:
    from pdf_extractor import parse_eversense_pdf
    HAS_PDF = True
except ImportError:
    HAS_PDF = False
    print("⚠️  PDF extractor not available")


def parse_documents():
    """Parse compatibility documents (DOCX preferred, PDF fallback)."""
    
    print("\n" + "="*70)
    print("🚀 COMPATIBILITY DATA EXTRACTION")
    print("="*70)
    
    us_data = None
    ous_data = None
    
    # Preference order: DOCX > PDF
    
    # === US Document ===
    us_docx = 'docx/compatibility_us.docx'
    us_pdf = 'pdf/compatibility_us.pdf'
    
    if HAS_DOCX and os.path.exists(us_docx):
        print(f"\n📄 Using: {us_docx}")
        us_data = parse_compatibility_docx(us_docx, region="US")
    elif HAS_PDF and os.path.exists(us_pdf):
        print(f"\n📄 Using: {us_pdf}")
        us_data = parse_eversense_pdf(us_pdf, region="US")
    else:
        print("\n❌ US document not found (tried .docx and .pdf)")
        return False
    
    # === OUS Document ===
    ous_docx = 'docx/compatibility_ous.docx'
    ous_pdf = 'pdf/compatibility_ous.pdf'
    
    if HAS_DOCX and os.path.exists(ous_docx):
        print(f"\n📄 Using: {ous_docx}")
        ous_data = parse_compatibility_docx(ous_docx, region="OUS")
    elif HAS_PDF and os.path.exists(ous_pdf):
        print(f"\n📄 Using: {ous_pdf}")
        ous_data = parse_eversense_pdf(ous_pdf, region="OUS")
    else:
        print("\n❌ OUS document not found (tried .docx and .pdf)")
        return False
    
    # === Merge Data ===
    merged_data = {
        "last_updated": datetime.now().isoformat(),
        "regions": {
            "US": us_data.get("document_info", {}) if us_data else {},
            "OUS": ous_data.get("document_info", {}) if ous_data else {}
        },
        "products": {
            "E3": {"android": [], "ios": []},
            "365": {"android": [], "ios": []},
            "NOW": {"android": [], "ios": []}
        }
    }
    
    # Merge products
    for product in ['E3', '365', 'NOW']:
        for os_type in ['android', 'ios']:
            if us_data:
                merged_data["products"][product][os_type].extend(
                    us_data["products"][product][os_type]
                )
            if ous_data:
                merged_data["products"][product][os_type].extend(
                    ous_data["products"][product][os_type]
                )
    
    # === Save Data ===
    os.makedirs('data', exist_ok=True)
    
    with open('data/compatibility.json', 'w', encoding='utf-8') as f:
        json.dump(merged_data, f, indent=2, ensure_ascii=False)
    
    # === Print Summary ===
    print("\n" + "="*70)
    print("✅ EXTRACTION COMPLETE")
    print("="*70)
    
    total_devices = 0
    for product in ['E3', '365', 'NOW']:
        ios = len(merged_data["products"][product]["ios"])
        android = len(merged_data["products"][product]["android"])
        product_total = ios + android
        total_devices += product_total
        
        print(f"\n{product}:")
        print(f"   📱 iOS: {ios}")
        print(f"   🤖 Android: {android}")
        print(f"   📊 Total: {product_total}")
    
    us_total = sum(
        len(merged_data["products"][p][os])
        for p in ['E3', '365', 'NOW']
        for os in ['android', 'ios']
        if any(d.get('region') == 'US' for d in merged_data["products"][p][os])
    )
    
    ous_total = sum(
        len(merged_data["products"][p][os])
        for p in ['E3', '365', 'NOW']
        for os in ['android', 'ios']
        if any(d.get('region') == 'OUS' for d in merged_data["products"][p][os])
    )
    
    print(f"\n{'='*70}")
    print(f"🌍 US Devices: {us_total}")
    print(f"🌎 OUS Devices: {ous_total}")
    print(f"📊 GRAND TOTAL: {total_devices} devices")
    print(f"💾 Saved to: data/compatibility.json")
    print(f"{'='*70}\n")
    
    return total_devices > 0


if __name__ == '__main__':
    success = parse_documents()
    sys.exit(0 if success else 1)
