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
except ImportError as e:
    HAS_DOCX = False
    print(f"⚠️  word_extractor not available: {e}")

# Try to import PDF extractor
try:
    from pdf_extractor import parse_eversense_pdf
    HAS_PDF = True
except ImportError as e:
    HAS_PDF = False
    print(f"⚠️  pdf_extractor not available: {e}")


def parse_documents():
    """Parse compatibility documents (DOCX preferred, PDF fallback)."""
    
    print("\n" + "="*70)
    print("🚀 COMPATIBILITY DATA EXTRACTION")
    print("="*70)
    
    us_data = None
    ous_data = None
    
    # === US Document ===
    us_docx = 'docx/compatibility_us.docx'
    us_pdf = 'pdf/compatibility_us.pdf'
    
    print(f"\n🔍 Looking for US document...")
    
    if HAS_DOCX and os.path.exists(us_docx):
        print(f"✅ Found: {us_docx}")
        us_data = parse_compatibility_docx(us_docx, region="US")
    elif HAS_PDF and os.path.exists(us_pdf):
        print(f"✅ Found: {us_pdf}")
        us_data = parse_eversense_pdf(us_pdf, region="US")
    else:
        print(f"❌ US document not found")
        print(f"   Checked: {us_docx}")
        print(f"   Checked: {us_pdf}")
        return False
    
    # === OUS Document ===
    ous_docx = 'docx/compatibility_ous.docx'
    ous_pdf = 'pdf/compatibility_ous.pdf'
    
    print(f"\n🔍 Looking for OUS document...")
    
    if HAS_DOCX and os.path.exists(ous_docx):
        print(f"✅ Found: {ous_docx}")
        ous_data = parse_compatibility_docx(ous_docx, region="OUS")
    elif HAS_PDF and os.path.exists(ous_pdf):
        print(f"✅ Found: {ous_pdf}")
        ous_data = parse_eversense_pdf(ous_pdf, region="OUS")
    else:
        print(f"❌ OUS document not found")
        print(f"   Checked: {ous_docx}")
        print(f"   Checked: {ous_pdf}")
        return False
    
    if not us_data or not ous_data:
        return False
    
    # === Merge Data ===
    merged_data = {
        "last_updated": datetime.now().isoformat(),
        "regions": {
            "US": us_data.get("document_info", {}),
            "OUS": ous_data.get("document_info", {})
        },
        "products": {
            "E3": {"android": [], "ios": []},
            "365": {"android": [], "ios": []},
            "NOW": {"android": [], "ios": []}
        }
    }
    
    # Merge products (remove duplicates)
    for product in ['E3', '365', 'NOW']:
        for os_type in ['android', 'ios']:
            seen = set()
            
            for device in us_data["products"][product][os_type]:
                key = f"{device['name']}|{device.get('region', 'US')}"
                if key not in seen:
                    merged_data["products"][product][os_type].append(device)
                    seen.add(key)
            
            for device in ous_data["products"][product][os_type]:
                key = f"{device['name']}|{device.get('region', 'OUS')}"
                if key not in seen:
                    merged_data["products"][product][os_type].append(device)
                    seen.add(key)
    
    # === Save Data ===
    os.makedirs('data', exist_ok=True)
    
    with open('data/compatibility.json', 'w', encoding='utf-8') as f:
        json.dump(merged_data, f, indent=2, ensure_ascii=False)
    
    # === Print Summary ===
    print("\n" + "="*70)
    print("✅ EXTRACTION COMPLETE")
    print("="*70)
    
    total_devices = 0
    us_total = 0
    ous_total = 0
    
    print("\n📊 Device Count by Product:")
    
    for product in ['E3', '365', 'NOW']:
        ios = len(merged_data["products"][product]["ios"])
        android = len(merged_data["products"][product]["android"])
        product_total = ios + android
        total_devices += product_total
        
        # Count by region
        for os_type in ['ios', 'android']:
            for device in merged_data["products"][product][os_type]:
                if device.get('region') == 'US':
                    us_total += 1
                elif device.get('region') == 'OUS':
                    ous_total += 1
        
        print(f"  {product}: {ios} iOS + {android} Android = {product_total}")
    
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
