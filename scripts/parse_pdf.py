#!/usr/bin/env python3
"""
Parse Eversense compatibility PDFs (US and OUS) with robust table detection.
"""

import pdfplumber
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
import sys
import os


def parse_eversense_pdf(pdf_path: str, region: str = "US") -> Dict[str, Any]:
    """Parse all tables from the Eversense compatibility PDF."""
    
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
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
    
    # More flexible table detection patterns
    table_patterns = [
        # Pattern: "Table 3 – Eversense E3 iOS MMA Compatible Handheld Devices"
        (r'Table\s*(\d+).*?E3.*?iOS', {"product": "E3", "os": "ios"}),
        (r'Table\s*(\d+).*?E3.*?Android', {"product": "E3", "os": "android"}),
        (r'Table\s*(\d+).*?365.*?iOS', {"product": "365", "os": "ios"}),
        (r'Table\s*(\d+).*?365.*?Android', {"product": "365", "os": "android"}),
        (r'Table\s*(\d+).*?NOW.*?iOS', {"product": "NOW", "os": "ios"}),
        (r'Table\s*(\d+).*?NOW.*?Android', {"product": "NOW", "os": "android"}),
    ]
    
    current_table = None
    in_table = False
    header_seen = False
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"📑 Total pages: {len(pdf.pages)}")
        
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if not text:
                print(f"   ⚠️ Page {page_num}: No text extracted")
                continue
            
            lines = text.split('\n')
            
            # Extract metadata
            for line in lines:
                if 'Revision:' in line or 'Rev:' in line:
                    match = re.search(r'Rev(?:ision)?:?\s*(\d+)', line)
                    if match and not compatibility_data["document_info"]["revision"]:
                        compatibility_data["document_info"]["revision"] = match.group(1)
                        print(f"   📌 Revision: {match.group(1)}")
                
                if 'Effective Date:' in line or 'Date:' in line:
                    match = re.search(r'(?:Effective\s+)?Date:?\s*(\d{1,2}\s+\w+\s+\d{4})', line)
                    if match and not compatibility_data["document_info"]["effective_date"]:
                        compatibility_data["document_info"]["effective_date"] = match.group(1).strip()
                        print(f"   📅 Effective Date: {match.group(1)}")
            
            # Process each line for table data
            for line_num, line in enumerate(lines):
                line_stripped = line.strip()
                
                if not line_stripped:
                    continue
                
                # Skip document headers/footers
                if any(skip in line_stripped for skip in [
                    'Confidential', 'Property of Senseonics', 
                    'Document #:', 'Title:', 'Page ', 'of '
                ]):
                    continue
                
                # Detect table start
                table_detected = False
                for pattern, config in table_patterns:
                    match = re.search(pattern, line_stripped, re.IGNORECASE)
                    if match:
                        # End previous table
                        if current_table and in_table:
                            product = current_table["product"]
                            os_type = current_table["os"]
                            count = len(compatibility_data["products"][product][os_type])
                            print(f"      ✅ {product}/{os_type}: {count} devices")
                        
                        # Start new table
                        current_table = config
                        in_table = True
                        header_seen = False
                        table_num = match.group(1) if match.lastindex else "?"
                        print(f"\n   {'📱' if config['os'] == 'ios' else '🤖'} Table {table_num}: {config['product']} {config['os'].upper()} (Page {page_num})")
                        table_detected = True
                        break
                
                if table_detected:
                    continue
                
                # Detect table header
                if in_table and not header_seen:
                    if 'Device Manufacturer' in line_stripped or 'Manufacturer' in line_stripped:
                        header_seen = True
                        print(f"      📋 Header found: {line_stripped[:60]}...")
                        continue
                
                # Parse device lines (only after header)
                if not in_table or not header_seen or not current_table:
                    continue
                
                # Skip revision history
                if re.match(r'^\d+\s+[A-Z][a-z]+\s+[A-Z][a-z]+', line_stripped):
                    if any(word in line_stripped for word in ['Updated', 'Added', 'Removed', 'Created']):
                        continue
                
                # Detect end of table (next table or major section)
                if re.search(r'(Revision\s+History|Table\s+\d+)', line_stripped, re.IGNORECASE):
                    if 'Table' not in line_stripped or not any(p[0] for p in table_patterns if re.search(p[0], line_stripped, re.IGNORECASE)):
                        # End of current table
                        if in_table and current_table:
                            product = current_table["product"]
                            os_type = current_table["os"]
                            count = len(compatibility_data["products"][product][os_type])
                            print(f"      ✅ {product}/{os_type}: {count} devices")
                        in_table = False
                        header_seen = False
                        continue
                
                # Parse device line
                device = parse_device_line_simple(
                    line_stripped, 
                    current_table["os"], 
                    current_table["product"],
                    region
                )
                
                if device:
                    product = current_table["product"]
                    os_type = current_table["os"]
                    
                    # Avoid duplicates
                    existing_names = [d['name'] for d in compatibility_data["products"][product][os_type]]
                    if device['name'] not in existing_names:
                        compatibility_data["products"][product][os_type].append(device)
        
        # End last table
        if current_table and in_table:
            product = current_table["product"]
            os_type = current_table["os"]
            count = len(compatibility_data["products"][product][os_type])
            print(f"      ✅ {product}/{os_type}: {count} devices")
    
    return compatibility_data


def parse_device_line_simple(line: str, os_type: str, product: str, region: str = "US") -> Optional[Dict[str, Any]]:
    """Parse a device line."""
    
    if len(line) < 5:
        return None
    
    if os_type == 'ios':
        return parse_ios_line_simple(line, product, region)
    else:
        return parse_android_line_simple(line, product, region)


def parse_ios_line_simple(line: str, product: str, region: str) -> Optional[Dict[str, Any]]:
    """Parse iOS device line."""
    
    if not line.startswith('Apple'):
        return None
    
    remaining = line[5:].strip()
    parts = re.split(r'\s{2,}', remaining)
    
    if len(parts) < 2:
        match = re.match(r'(.+?)\s+([A-Z0-9]{5,}(?:LL/A)?|Rationally\s+Qualified)$', remaining)
        if match:
            device_model = match.group(1).strip()
            model_number = match.group(2).strip()
        else:
            device_model = remaining
            model_number = ""
    else:
        device_model = parts[0].strip()
        model_number = parts[1].strip() if len(parts) > 1 else ""
    
    device_model_clean = re.sub(r'\s*\(\d+\s*mm\)', '', device_model).strip()
    device_model_clean = re.sub(r'\s*\([^)]*\)', '', device_model_clean).strip()
    
    rationally_qualified = 'rationally qualified' in line.lower()
    device_name = f"Apple {device_model_clean}"
    os_version = extract_ios_version(device_model_clean)
    
    return {
        "name": device_name,
        "manufacturer": "Apple",
        "model": device_model_clean,
        "model_number": model_number if model_number and 'Rationally' not in model_number else '',
        "os_version": os_version,
        "rationally_qualified": rationally_qualified,
        "product": product,
        "region": region
    }


def parse_android_line_simple(line: str, product: str, region: str) -> Optional[Dict[str, Any]]:
    """Parse Android device line."""
    
    manufacturers = [
        'Google', 'Samsung', 'OnePlus', 'Motorola', 'LG', 'HTC', 'Nokia', 
        'HMD Global', 'Lively', 'TCL', 'Xiaomi', 'Sony', 'Huawei', 'Oppo', 
        'Vivo', 'Asus', 'ZTE', 'Lenovo', 'Realme'
    ]
    
    manufacturer = None
    for mfr in manufacturers:
        if line.startswith(mfr):
            manufacturer = mfr
            break
    
    if not manufacturer:
        return None
    
    remaining = line[len(manufacturer):].strip()
    
    # Extract RQ from end
    rq_pattern = r'\s+(Yes|No\s*\([^)]+\))\s*$'
    rq_match = re.search(rq_pattern, remaining, re.IGNORECASE)
    
    rationally_qualified = False
    model_number = ""
    
    if rq_match:
        rq_text = rq_match.group(1).strip()
        remaining = remaining[:rq_match.start()].strip()
        
        if rq_text.lower() == 'yes':
            rationally_qualified = True
        else:
            no_match = re.search(r'No\s*\(([^)]+)\)', rq_text, re.IGNORECASE)
            if no_match:
                model_number = no_match.group(1).strip()
    
    # Parse model name
    parts = re.split(r'\s{2,}', remaining)
    
    if len(parts) >= 2:
        model_name = parts[0].strip()
        if not model_number and parts[1] and parts[1].lower() != model_name.lower():
            model_number = parts[1].strip()
    else:
        words = remaining.split()
        model_name = None
        
        mid = len(words) // 2
        if mid > 0:
            first_half = ' '.join(words[:mid])
            second_half = ' '.join(words[mid:mid*2])
            
            if first_half == second_half:
                model_name = first_half
            else:
                for i in range(1, len(words)):
                    first_part = ' '.join(words[:i])
                    rest = ' '.join(words[i:])
                    
                    if rest.startswith(first_part):
                        model_name = first_part
                        break
        
        if not model_name:
            model_name = remaining
    
    device_name = f"{manufacturer} {model_name}"
    os_version = extract_android_version(model_name)
    
    return {
        "name": device_name,
        "manufacturer": manufacturer,
        "model": model_name,
        "model_number": model_number,
        "os_version": os_version,
        "rationally_qualified": rationally_qualified,
        "product": product,
        "region": region
    }


def extract_ios_version(model_name: str) -> str:
    """Extract iOS version."""
    model_lower = model_name.lower()
    
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
    elif 'iphone 11' in model_lower:
        return '13.0'
    
    return '12.0'


def extract_android_version(model_name: str) -> str:
    """Extract Android version."""
    model_lower = model_name.lower()
    
    if 'pixel 10' in model_lower or 'pixel 9' in model_lower:
        return '14.0'
    elif 'pixel 8' in model_lower:
        return '14.0'
    elif 'pixel 7' in model_lower:
        return '13.0'
    
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
        us_data = {"products": {"E3": {"android": [], "ios": []}, "365": {"android": [], "ios": []}, "NOW": {"android": [], "ios": []}}}
        ous_data = {"products": {"E3": {"android": [], "ios": []}, "365": {"android": [], "ios": []}, "NOW": {"android": [], "ios": []}}}
        
        if os.path.exists(us_pdf):
            us_data = parse_eversense_pdf(us_pdf, region="US")
        else:
            print(f"⚠️  US PDF not found: {us_pdf}")
        
        if os.path.exists(ous_pdf):
            ous_data = parse_eversense_pdf(ous_pdf, region="OUS")
        else:
            print(f"⚠️  OUS PDF not found: {ous_pdf}")
        
        merged_data = merge_compatibility_data(us_data, ous_data)
        
        os.makedirs('data', exist_ok=True)
        output_file = 'data/compatibility.json'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*60}")
        print(f"✅ PARSING COMPLETED")
        print(f"{'='*60}")
        
        total = 0
        for product in ['E3', '365', 'NOW']:
            ios_count = len(merged_data["products"][product]["ios"])
            android_count = len(merged_data["products"][product]["android"])
            total += ios_count + android_count
            
            print(f"\n{product}:")
            print(f"   📱 iOS: {ios_count}")
            print(f"   🤖 Android: {android_count}")
        
        us_count = sum(1 for p in ['E3', '365', 'NOW'] for os in ['ios', 'android'] for d in merged_data["products"][p][os] if d.get('region') == 'US')
        ous_count = sum(1 for p in ['E3', '365', 'NOW'] for os in ['ios', 'android'] for d in merged_data["products"][p][os] if d.get('region') == 'OUS')
        
        print(f"\n{'='*60}")
        print(f"🌍 US: {us_count} | 🌎 OUS: {ous_count} | 📊 TOTAL: {total}")
        print(f"💾 Saved to: {output_file}")
        
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
