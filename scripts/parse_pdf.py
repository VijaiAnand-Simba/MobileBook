#!/usr/bin/env python3
"""
Main PDF parser using universal extractor.
"""

from pdf_extractor import UniversalPDFExtractor, parse_eversense_pdf
import json
import os
import sys
from datetime import datetime


def merge_compatibility_data(us_data: Dict, ous_data: Dict) -> Dict:
    """Merge US and OUS data."""
    
    merged = {
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
    
    for product in ['E3', '365', 'NOW']:
        for os_type in ['android', 'ios']:
            if us_data.get("products", {}).get(product, {}).get(os_type):
                merged["products"][product][os_type].extend(us_data["products"][product][os_type])
            
            if ous_data.get("products", {}).get(product, {}).get(os_type):
                merged["products"][product][os_type].extend(ous_data["products"][product][os_type])
    
    return merged


if __name__ == '__main__':
    us_pdf = 'pdf/compatibility_us.pdf'
    ous_pdf = 'pdf/compatibility_ous.pdf'
    
    try:
        us_data = {"products": {"E3": {"android": [], "ios": []}, "365": {"android": [], "ios": []}, "NOW": {"android": [], "ios": []}}}
        ous_data = {"products": {"E3": {"android": [], "ios": []}, "365": {"android": [], "ios": []}, "NOW": {"android": [], "ios": []}}}
        
        if os.path.exists(us_pdf):
            us_data = parse_eversense_pdf(us_pdf, region="US")
        else:
            print(f"⚠️  US PDF not found")
        
        if os.path.exists(ous_pdf):
            ous_data = parse_eversense_pdf(ous_pdf, region="OUS")
        else:
            print(f"⚠️  OUS PDF not found")
        
        merged_data = merge_compatibility_data(us_data, ous_data)
        
        os.makedirs('data', exist_ok=True)
        with open('data/compatibility.json', 'w') as f:
            json.dump(merged_data, f, indent=2)
        
        print(f"\n{'='*70}")
        print(f"✅ EXTRACTION COMPLETE")
        print(f"{'='*70}")
        
        total = sum(len(merged_data["products"][p][os]) for p in ['E3', '365', 'NOW'] for os in ['ios', 'android'])
        
        for product in ['E3', '365', 'NOW']:
            ios_count = len(merged_data["products"][product]["ios"])
            android_count = len(merged_data["products"][product]["android"])
            print(f"\n{product}: iOS={ios_count}, Android={android_count}")
        
        print(f"\n📊 TOTAL: {total} devices")
        
        sys.exit(0 if total > 0 else 1)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
