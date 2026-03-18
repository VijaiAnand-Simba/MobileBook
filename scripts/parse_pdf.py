#!/usr/bin/env python3
"""
Main PDF parser using universal extractor.
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional

try:
    from pdf_extractor import UniversalPDFExtractor, parse_eversense_pdf
    USE_UNIVERSAL = True
except ImportError:
    print("⚠️  Universal extractor not available, using fallback method")
    USE_UNIVERSAL = False
    import pdfplumber
    import re


def parse_eversense_pdf_fallback(pdf_path: str, region: str = "US") -> Dict[str, Any]:
    """Fallback parser using pdfplumber only."""
    
    print(f"\n📄 Reading PDF: {pdf_path} ({region})")
    
    compatibility_data = {
        "region": region,
        "last_updated": datetime.now().isoformat(),
        "document_info": {
            "revision": None,
            "effective_date": None,
            "source_file": os.path.basename(pdf_path)
        },
        "products": {
            "E3": {"android": [], "ios": []},
            "365": {"android": [], "ios": []},
            "NOW": {"android": [], "ios": []}
        }
    }
    
    table_patterns = [
        (r'E3.*?iOS', {"product": "E3", "os": "ios"}),
        (r'E3.*?Android', {"product": "E3", "os": "android"}),
        (r'365.*?iOS', {"product": "365", "os": "ios"}),
        (r'365.*?Android', {"product": "365", "os": "android"}),
        (r'NOW.*?iOS', {"product": "NOW", "os": "ios"}),
        (r'NOW.*?Android', {"product": "NOW", "os": "android"}),
    ]
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"📑 Total pages: {len(pdf.pages)}")
            
            for page_num, page in enumerate(pdf.pages, 1):
                # Try to extract tables directly
                tables = page.extract_tables()
                
                if tables:
                    text = page.extract_text()
                    current_table = None
                    
                    # Find which table this is
                    for pattern, config in table_patterns:
                        if text and re.search(pattern, text, re.IGNORECASE):
                            current_table = config
                            break
                    
                    if current_table:
                        for table in tables:
                            if not table or len(table) < 2:
                                continue
                            
                            devices_found = 0
                            
                            # Parse table rows (skip header)
                            for row in table[1:]:
                                if not row:
                                    continue
                                
                                # Clean row
                                clean_row = [str(cell).strip() if cell else '' for cell in row]
                                clean_row = [c for c in clean_row if c]
                                
                                if len(clean_row) < 2:
                                    continue
                                
                                device = parse_table_row(
                                    clean_row, 
                                    current_table['os'], 
                                    current_table['product'],
                                    region
                                )
                                
                                if device:
                                    product = current_table["product"]
                                    os_type = current_table["os"]
                                    
                                    # Check for duplicates
                                    existing = [d['name'] for d in compatibility_data["products"][product][os_type]]
                                    if device['name'] not in existing:
                                        compatibility_data["products"][product][os_type].append(device)
                                        devices_found += 1
                            
                            if devices_found > 0:
                                print(f"   {'📱' if current_table['os'] == 'ios' else '🤖'} {current_table['product']} {current_table['os'].upper()}: {devices_found} devices")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    return compatibility_data


def parse_table_row(row: List[str], os_type: str, product: str, region: str) -> Optional[Dict[str, Any]]:
    """Parse a table row into a device dict."""
    
    if os_type == 'ios':
        # iOS format: [Manufacturer, Model, Model Number]
        if row[0].lower() != 'apple':
            return None
        
        model = row[1] if len(row) > 1 else ''
        model_number = row[2] if len(row) > 2 else ''
        
        if not model:
            return None
        
        # Clean model name
        model = re.sub(r'\s*\(\d+\s*mm\)', '', model).strip()
        
        return {
            "name": f"Apple {model}",
            "manufacturer": "Apple",
            "model": model,
            "model_number": model_number if 'Rationally' not in model_number else '',
            "os_version": extract_ios_version(model),
            "rationally_qualified": 'rationally qualified' in ' '.join(row).lower(),
            "product": product,
            "region": region
        }
    
    else:
        # Android format: [Manufacturer, Model, Model Number, RQ]
        manufacturers = ['Google', 'Samsung', 'OnePlus', 'Motorola', 'LG', 'HTC', 'Nokia', 
                        'HMD Global', 'Sony', 'Xiaomi', 'Oppo', 'Vivo', 'Realme', 'Lively', 'TCL']
        
        manufacturer = None
        for mfr in manufacturers:
            if row[0] == mfr or row[0].lower() == mfr.lower():
                manufacturer = mfr
                break
        
        if not manufacturer:
            return None
        
        model = row[1] if len(row) > 1 else ''
        
        if not model:
            return None
        
        # Extract RQ and model number
        rq = False
        model_number = ''
        
        if len(row) > 2:
            # Last column might be RQ status
            last_col = row[-1]
            
            if last_col.lower() == 'yes':
                rq = True
            elif 'no (' in last_col.lower():
                match = re.search(r'No\s*\(([^)]+)\)', last_col, re.IGNORECASE)
                if match:
                    model_number = match.group(1)
            elif len(row) > 2 and row[-2]:
                model_number = row[-2]
        
        return {
            "name": f"{manufacturer} {model}",
            "manufacturer": manufacturer,
            "model": model,
            "model_number": model_number,
            "os_version": extract_android_version(model),
            "rationally_qualified": rq,
            "product": product,
            "region": region
        }


def extract_ios_version(model: str) -> str:
    """Extract iOS version from model name."""
    model_lower = model.lower()
    
    if 'iphone 17' in model_lower:
        return '19.0'
    elif 'iphone 16' in model_lower:
        return '18.0'
    elif 'iphone 15' in model_lower:
        return '17.0'
    elif 'iphone 14' in model_lower:
        return '16.0'
    elif 'iphone 13' in model_lower:
        return '15.0'
    elif 'iphone 12' in model_lower:
        return '14.0'
    elif 'watch' in model_lower:
        return '9.0'
    
    return '12.0'


def extract_android_version(model: str) -> str:
    """Extract Android version from model name."""
    model_lower = model.lower()
    
    if 'pixel 10' in model_lower or 'pixel 9' in model_lower:
        return '14.0'
    elif 'pixel 8' in model_lower:
        return '14.0'
    elif 'pixel 7' in model_lower:
        return '13.0'
    elif 's26' in model_lower or 's25' in model_lower:
        return '15.0'
    elif 's24' in model_lower:
        return '14.0'
    
    return '10.0'


def merge_compatibility_data(us_data: Dict[str, Any], ous_data: Dict[str, Any]) -> Dict[str, Any]:
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
        # Initialize empty data
        us_data: Dict[str, Any] = {
            "products": {
                "E3": {"android": [], "ios": []}, 
                "365": {"android": [], "ios": []}, 
                "NOW": {"android": [], "ios": []}
            }
        }
        ous_data: Dict[str, Any] = {
            "products": {
                "E3": {"android": [], "ios": []}, 
                "365": {"android": [], "ios": []}, 
                "NOW": {"android": [], "ios": []}
            }
        }
        
        # Parse PDFs
        if os.path.exists(us_pdf):
            if USE_UNIVERSAL:
                us_data = parse_eversense_pdf(us_pdf, region="US")
            else:
                us_data = parse_eversense_pdf_fallback(us_pdf, region="US")
        else:
            print(f"⚠️  US PDF not found: {us_pdf}")
        
        if os.path.exists(ous_pdf):
            if USE_UNIVERSAL:
                ous_data = parse_eversense_pdf(ous_pdf, region="OUS")
            else:
                ous_data = parse_eversense_pdf_fallback(ous_pdf, region="OUS")
        else:
            print(f"⚠️  OUS PDF not found: {ous_pdf}")
        
        # Merge data
        merged_data = merge_compatibility_data(us_data, ous_data)
        
        # Save output
        os.makedirs('data', exist_ok=True)
        output_file = 'data/compatibility.json'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, indent=2, ensure_ascii=False)
        
        # Print summary
        print(f"\n{'='*70}")
        print(f"✅ PARSING COMPLETED")
        print(f"{'='*70}")
        
        total = 0
        for product in ['E3', '365', 'NOW']:
            ios_count = len(merged_data["products"][product]["ios"])
            android_count = len(merged_data["products"][product]["android"])
            product_total = ios_count + android_count
            total += product_total
            
            print(f"\n{product}:")
            print(f"   📱 iOS: {ios_count}")
            print(f"   🤖 Android: {android_count}")
            print(f"   📊 Total: {product_total}")
        
        us_count = sum(1 for p in ['E3', '365', 'NOW'] 
                      for os in ['ios', 'android'] 
                      for d in merged_data["products"][p][os] 
                      if d.get('region') == 'US')
        
        ous_count = sum(1 for p in ['E3', '365', 'NOW'] 
                       for os in ['ios', 'android'] 
                       for d in merged_data["products"][p][os] 
                       if d.get('region') == 'OUS')
        
        print(f"\n{'='*70}")
        print(f"🌍 US Devices: {us_count}")
        print(f"🌎 OUS Devices: {ous_count}")
        print(f"📊 GRAND TOTAL: {total} devices")
        print(f"💾 Saved to: {output_file}")
        
        # Exit with error if no devices found
        if total == 0:
            print("\n⚠️  WARNING: No devices were extracted!")
            sys.exit(1)
        
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
