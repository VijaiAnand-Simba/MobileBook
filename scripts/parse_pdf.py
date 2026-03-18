#!/usr/bin/env python3
"""
Parse Eversense compatibility PDFs (US and OUS) using line-by-line extraction.
"""

import pdfplumber
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
import sys
import os

def parse_eversense_pdf(pdf_path: str, region: str = "US") -> Dict[str, Any]:
    """Parse all 6 tables from the Eversense compatibility PDF."""
    
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    print(f"📄 Reading PDF: {pdf_path} ({region})")
    
    compatibility_data = {
        "region": region,
        "last_updated": datetime.now().isoformat(),
        "document_info": {
            "revision": None,
            "effective_date": None,
            "source_file": os.path.basename(pdf_path)
        },
        "products": {
            "E3": {
                "android": [],
                "ios": []
            },
            "365": {
                "android": [],
                "ios": []
            },
            "NOW": {
                "android": [],
                "ios": []
            }
        }
    }
    
    # Table configurations
    table_configs = {
        3: {"product": "E3", "os": "ios", "name": "E3 iOS MMA"},
        4: {"product": "E3", "os": "android", "name": "E3 Android MMA"},
        5: {"product": "365", "os": "ios", "name": "365 iOS MMA"},
        6: {"product": "365", "os": "android", "name": "365 Android MMA"},
        7: {"product": "NOW", "os": "ios", "name": "NOW iOS App"},
        8: {"product": "NOW", "os": "android", "name": "NOW Android App"}
    }
    
    current_table_num = None
    in_table = False
    table_header_seen = False
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"📑 Total pages: {len(pdf.pages)}\n")
        
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if not text:
                continue
            
            lines = text.split('\n')
            
            # Extract metadata
            for line in lines:
                if 'Revision:' in line:
                    revision_match = re.search(r'Revision:\s*(\d+)', line)
                    if revision_match and not compatibility_data["document_info"]["revision"]:
                        compatibility_data["document_info"]["revision"] = revision_match.group(1)
                
                if 'Effective Date:' in line:
                    date_match = re.search(r'Effective Date:\s*(\d{1,2}\s+\w+\s+\d{4})', line)
                    if date_match and not compatibility_data["document_info"]["effective_date"]:
                        compatibility_data["document_info"]["effective_date"] = date_match.group(1).strip()
            
            # Process each line
            for line in lines:
                line_stripped = line.strip()
                
                if not line_stripped:
                    continue
                
                if any(skip in line_stripped for skip in ['Confidential', 'Property of Senseonics', 'Document #:', 'Title:', 'Pages:']):
                    continue
                
                # Detect table start
                table_detected = False
                for tnum in range(3, 9):
                    if f"Table {tnum}" in line_stripped:
                        if current_table_num and in_table:
                            config = table_configs[current_table_num]
                            count = len(compatibility_data["products"][config["product"]][config["os"]])
                            print(f"   ✅ Table {current_table_num}: {count} devices\n")
                        
                        current_table_num = tnum
                        in_table = True
                        table_header_seen = False
                        config = table_configs[tnum]
                        print(f"{'📱' if config['os'] == 'ios' else '🤖'} Found Table {tnum} - {config['name']} (Page {page_num})")
                        table_detected = True
                        break
                
                if table_detected:
                    continue
                
                if 'Device Manufacturer' in line_stripped or 'Device Model' in line_stripped:
                    table_header_seen = True
                    continue
                
                if not in_table or not table_header_seen or not current_table_num:
                    continue
                
                if re.match(r'^\d+\s+[A-Z][a-z]+\s+[A-Z][a-z]+', line_stripped):
                    if 'Updated' in line_stripped or 'Added' in line_stripped or 'Removed' in line_stripped:
                        continue
                
                config = table_configs[current_table_num]
                device = parse_device_line_simple(line_stripped, config["os"], config["product"], region)
                
                if device:
                    product = config["product"]
                    os_type = config["os"]
                    
                    existing_names = [d['name'] for d in compatibility_data["products"][product][os_type]]
                    if device['name'] not in existing_names:
                        compatibility_data["products"][product][os_type].append(device)
        
        if current_table_num and in_table:
            config = table_configs[current_table_num]
            count = len(compatibility_data["products"][config["product"]][config["os"]])
            print(f"   ✅ Table {current_table_num}: {count} devices\n")
    
    return compatibility_data


def merge_compatibility_data(us_data: Dict[str, Any], ous_data: Dict[str, Any]) -> Dict[str, Any]:
    """Merge US and OUS compatibility data."""
    
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
    
    # Merge devices from both regions
    for product in ['E3', '365', 'NOW']:
        for os_type in ['android', 'ios']:
            # Add US devices
            if us_data.get("products", {}).get(product, {}).get(os_type):
                merged["products"][product][os_type].extend(us_data["products"][product][os_type])
            
            # Add OUS devices
            if ous_data.get("products", {}).get(product, {}).get(os_type):
                merged["products"][product][os_type].extend(ous_data["products"][product][os_type])
    
    return merged


def parse_device_line_simple(line: str, os_type: str, product: str, region: str = "US") -> Optional[Dict[str, Any]]:
    """Parse a device line using simple text splitting."""
    
    if len(line) < 5:
        return None
    
    if os_type == 'ios':
        return parse_ios_line_simple(line, product, region)
    else:
        return parse_android_line_simple(line, product, region)


def parse_ios_line_simple(line: str, product: str, region: str) -> Optional[Dict[str, Any]]:
    """Parse iOS device line (3 columns)."""
    
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
    """Parse Android device line (4 columns)."""
    
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
    
    # Extract RQ column from the END
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
    """Extract iOS version from device model."""
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
    elif 'iphone xs' in model_lower or 'iphone xr' in model_lower or 'iphone x' in model_lower:
        return '12.0'
    elif 'iphone 8' in model_lower:
        return '11.0'
    elif 'se 3' in model_lower or 'se (3' in model_lower:
        return '15.0'
    elif 'se 2' in model_lower or 'se (2' in model_lower:
        return '13.0'
    elif 'watch' in model_lower:
        return '9.0'
    elif 'ipad' in model_lower:
        return '15.0'
    
    return '12.0'


def extract_android_version(model_name: str) -> str:
    """Extract Android version from device model."""
    model_lower = model_name.lower()
    
    if 'pixel 10' in model_lower or 'pixel 9' in model_lower:
        return '14.0'
    elif 'pixel 8' in model_lower:
        return '14.0'
    elif 'pixel 7' in model_lower:
        return '13.0'
    elif 'pixel 6' in model_lower:
        return '12.0'
    elif 'pixel 5' in model_lower or 'pixel 4' in model_lower:
        return '11.0'
    elif 's25' in model_lower or 's24' in model_lower:
        return '14.0'
    elif 's23' in model_lower or 's22' in model_lower:
        return '13.0'
    elif 's21' in model_lower or 's20' in model_lower:
        return '11.0'
    elif '2025' in model_lower:
        return '15.0'
    elif '2024' in model_lower:
        return '14.0'
    elif '2023' in model_lower:
        return '13.0'
    
    return '10.0'


if __name__ == '__main__':
    us_pdf = 'pdf/compatibility_us.pdf'
    ous_pdf = 'pdf/compatibility_ous.pdf'
    
    try:
        # Parse US PDF
        us_data = None
        if os.path.exists(us_pdf):
            us_data = parse_eversense_pdf(us_pdf, region="US")
        else:
            print(f"⚠️  US PDF not found: {us_pdf}")
            us_data = {"products": {"E3": {"android": [], "ios": []}, "365": {"android": [], "ios": []}, "NOW": {"android": [], "ios": []}}}
        
        # Parse OUS PDF
        ous_data = None
        if os.path.exists(ous_pdf):
            ous_data = parse_eversense_pdf(ous_pdf, region="OUS")
        else:
            print(f"⚠️  OUS PDF not found: {ous_pdf}")
            ous_data = {"products": {"E3": {"android": [], "ios": []}, "365": {"android": [], "ios": []}, "NOW": {"android": [], "ios": []}}}
        
        # Merge both datasets
        merged_data = merge_compatibility_data(us_data, ous_data)
        
        # Save to JSON
        os.makedirs('data', exist_ok=True)
        output_file = 'data/compatibility.json'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, indent=2, ensure_ascii=False)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"✅ PARSING COMPLETED")
        print(f"{'='*60}")
        
        total_devices = 0
        for product in ['E3', '365', 'NOW']:
            ios_count = len(merged_data["products"][product]["ios"])
            android_count = len(merged_data["products"][product]["android"])
            product_total = ios_count + android_count
            total_devices += product_total
            
            print(f"\n{product}:")
            print(f"   📱 iOS: {ios_count} devices")
            print(f"   🤖 Android: {android_count} devices")
            print(f"   📊 Total: {product_total} devices")
        
        # Count by region
        us_count = sum(1 for p in ['E3', '365', 'NOW'] for os in ['ios', 'android'] for d in merged_data["products"][p][os] if d.get('region') == 'US')
        ous_count = sum(1 for p in ['E3', '365', 'NOW'] for os in ['ios', 'android'] for d in merged_data["products"][p][os] if d.get('region') == 'OUS')
        
        print(f"\n{'='*60}")
        print(f"🌍 US Devices: {us_count}")
        print(f"🌎 OUS Devices: {ous_count}")
        print(f"📊 GRAND TOTAL: {total_devices} devices")
        print(f"💾 Saved to: {output_file}")
        
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error parsing PDF: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
