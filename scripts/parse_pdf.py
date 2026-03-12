#!/usr/bin/env python3
"""
Parse Eversense compatibility PDF using line-by-line extraction.
More robust than table extraction for complex PDFs.
"""

import pdfplumber
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
import sys
import os

def parse_eversense_pdf(pdf_path: str) -> Dict[str, Any]:
    """Parse all 6 tables from the Eversense compatibility PDF."""
    
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    print(f"📄 Reading PDF: {pdf_path}")
    
    compatibility_data = {
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
                
                # Skip empty lines
                if not line_stripped:
                    continue
                
                # Skip confidential markers
                if any(skip in line_stripped for skip in ['Confidential', 'Property of Senseonics', 'Document #:', 'Title:', 'Pages:']):
                    continue
                
                # Detect table start
                table_detected = False
                for tnum in range(3, 9):
                    if f"Table {tnum}" in line_stripped:
                        # End previous table
                        if current_table_num and in_table:
                            config = table_configs[current_table_num]
                            count = len(compatibility_data["products"][config["product"]][config["os"]])
                            print(f"   ✅ Table {current_table_num}: {count} devices\n")
                        
                        # Start new table
                        current_table_num = tnum
                        in_table = True
                        table_header_seen = False
                        config = table_configs[tnum]
                        print(f"{'📱' if config['os'] == 'ios' else '🤖'} Found Table {tnum} - {config['name']} (Page {page_num})")
                        table_detected = True
                        break
                
                if table_detected:
                    continue
                
                # Skip table headers
                if 'Device Manufacturer' in line_stripped or 'Device Model' in line_stripped:
                    table_header_seen = True
                    continue
                
                # Only process if we're in a table and past the header
                if not in_table or not table_header_seen or not current_table_num:
                    continue
                
                # Skip revision history entries (specific pattern)
                if re.match(r'^\d+\s+[A-Z][a-z]+\s+[A-Z][a-z]+', line_stripped):
                    # This looks like "34 Alekya Bethi" - revision history
                    if 'Updated' in line_stripped or 'Added' in line_stripped or 'Removed' in line_stripped:
                        continue
                
                # Parse the device line
                config = table_configs[current_table_num]
                device = parse_device_line_simple(line_stripped, config["os"], config["product"])
                
                if device:
                    product = config["product"]
                    os_type = config["os"]
                    
                    # Avoid duplicates
                    existing_names = [d['name'] for d in compatibility_data["products"][product][os_type]]
                    if device['name'] not in existing_names:
                        compatibility_data["products"][product][os_type].append(device)
        
        # End last table
        if current_table_num and in_table:
            config = table_configs[current_table_num]
            count = len(compatibility_data["products"][config["product"]][config["os"]])
            print(f"   ✅ Table {current_table_num}: {count} devices\n")
    
    # Save to JSON
    os.makedirs('data', exist_ok=True)
    output_file = 'data/compatibility.json'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(compatibility_data, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"✅ PARSING COMPLETED")
    print(f"{'='*60}")
    
    total_devices = 0
    for product in ['E3', '365', 'NOW']:
        ios_count = len(compatibility_data["products"][product]["ios"])
        android_count = len(compatibility_data["products"][product]["android"])
        product_total = ios_count + android_count
        total_devices += product_total
        
        print(f"\n{product}:")
        print(f"   📱 iOS: {ios_count} devices")
        print(f"   🤖 Android: {android_count} devices")
        print(f"   📊 Total: {product_total} devices")
    
    print(f"\n{'='*60}")
    print(f"📊 GRAND TOTAL: {total_devices} devices")
    print(f"💾 Saved to: {output_file}")
    
    return compatibility_data


def parse_device_line_simple(line: str, os_type: str, product: str) -> Optional[Dict[str, Any]]:
    """
    Parse a device line using simple text splitting.
    More reliable than table extraction.
    """
    
    # Skip lines that are too short
    if len(line) < 5:
        return None
    
    # iOS format: Manufacturer | Model | Model Number (3 columns, space-separated)
    if os_type == 'ios':
        return parse_ios_line_simple(line, product)
    else:
        # Android format: Manufacturer | Model Name | Model Number | RQ (4 columns)
        return parse_android_line_simple(line, product)


def parse_ios_line_simple(line: str, product: str) -> Optional[Dict[str, Any]]:
    """Parse iOS device line (3 columns)."""
    
    # Must start with "Apple"
    if not line.startswith('Apple'):
        return None
    
    # Remove "Apple" and process the rest
    remaining = line[5:].strip()
    
    # Split on multiple spaces (usually 2+ spaces separate columns)
    parts = re.split(r'\s{2,}', remaining)
    
    if len(parts) < 2:
        # Try splitting on common model number patterns
        # Format: "iPhone 14 Pro MPXT3LL/A"
        match = re.match(r'(.+?)\s+([A-Z0-9]{5,}(?:LL/A)?|Rationally\s+Qualified)$', remaining)
        if match:
            device_model = match.group(1).strip()
            model_number = match.group(2).strip()
        else:
            # No clear model number, everything is the device model
            device_model = remaining
            model_number = ""
    else:
        device_model = parts[0].strip()
        model_number = parts[1].strip() if len(parts) > 1 else ""
    
    # Clean device model (remove size info)
    device_model_clean = re.sub(r'\s*\(\d+\s*mm\)', '', device_model).strip()
    device_model_clean = re.sub(r'\s*\([^)]*\)', '', device_model_clean).strip()
    
    # Check if rationally qualified
    rationally_qualified = 'rationally qualified' in line.lower()
    
    # Build device name
    device_name = f"Apple {device_model_clean}"
    
    # Get OS version
    os_version = extract_ios_version(device_model_clean)
    
    return {
        "name": device_name,
        "manufacturer": "Apple",
        "model": device_model_clean,
        "model_number": model_number if model_number and 'Rationally' not in model_number else '',
        "os_version": os_version,
        "rationally_qualified": rationally_qualified,
        "product": product
    }


def parse_android_line_simple(line: str, product: str) -> Optional[Dict[str, Any]]:
    """
    Parse Android device line (4 columns).
    
    Strategy: Parse from RIGHT to LEFT since the RQ column has a clear pattern.
    
    Format: Manufacturer | Model Name | Model Number (optional) | RQ (Yes or No (XXX))
    Example: "Google Pixel 2 XL Pixel 2 XL No (G011C)"
    Example: "Google Pixel 4 Pixel 4 Yes"
    """
    
    # Known manufacturers
    manufacturers = [
        'Google', 'Samsung', 'OnePlus', 'Motorola', 'LG', 'HTC', 'Nokia', 
        'HMD Global', 'Lively', 'TCL', 'Xiaomi', 'Sony', 'Huawei', 'Oppo', 
        'Vivo', 'Asus', 'ZTE', 'Lenovo', 'Realme'
    ]
    
    # Find which manufacturer this line starts with
    manufacturer = None
    for mfr in manufacturers:
        if line.startswith(mfr):
            manufacturer = mfr
            break
    
    if not manufacturer:
        return None
    
    # Remove manufacturer from line
    remaining = line[len(manufacturer):].strip()
    
    # Step 1: Extract RQ column from the END (Yes or No (XXX))
    # Match "Yes" or "No (something)" at the end of the line
    rq_pattern = r'\s+(Yes|No\s*\([^)]+\))\s*$'
    rq_match = re.search(rq_pattern, remaining, re.IGNORECASE)
    
    rationally_qualified = False
    model_number = ""
    
    if rq_match:
        rq_text = rq_match.group(1).strip()
        # Remove the RQ column from remaining text
        remaining = remaining[:rq_match.start()].strip()
        
        # Parse RQ value
        if rq_text.lower() == 'yes':
            rationally_qualified = True
        else:
            # Extract model number from "No (G011C)"
            no_match = re.search(r'No\s*\(([^)]+)\)', rq_text, re.IGNORECASE)
            if no_match:
                model_number = no_match.group(1).strip()
    
    # Step 2: What's left is "Model Name" possibly repeated or "Model Name Model_Ref"
    # Common pattern: "Pixel 2 XL Pixel 2 XL" (model name repeated)
    
    # Try to split on 2+ spaces first (in case there are any)
    parts = re.split(r'\s{2,}', remaining)
    
    if len(parts) >= 2:
        # Clear column separation exists
        model_name = parts[0].strip()
        # parts[1] could be a model reference, but we prioritize model_number from RQ
        if not model_number and parts[1] and parts[1].lower() != model_name.lower():
            model_number = parts[1].strip()
    else:
        # No clear separation - model name might be repeated with single spaces
        # Try to detect if first half equals second half
        words = remaining.split()
        model_name = None
        
        # Try splitting in half
        mid = len(words) // 2
        if mid > 0:
            first_half = ' '.join(words[:mid])
            second_half = ' '.join(words[mid:mid*2])
            
            if first_half == second_half:
                # Model name is repeated exactly
                model_name = first_half
            else:
                # Try finding the split point where duplication starts
                for i in range(1, len(words)):
                    first_part = ' '.join(words[:i])
                    rest = ' '.join(words[i:])
                    
                    # Check if rest starts with first_part
                    if rest.startswith(first_part):
                        model_name = first_part
                        break
        
        # If still no model name found, use the entire remaining text
        if not model_name:
            model_name = remaining
    
    # Build device name
    device_name = f"{manufacturer} {model_name}"
    
    # Get Android version
    os_version = extract_android_version(model_name)
    
    return {
        "name": device_name,
        "manufacturer": manufacturer,
        "model": model_name,
        "model_number": model_number,
        "os_version": os_version,
        "rationally_qualified": rationally_qualified,
        "product": product
    }


def extract_ios_version(model_name: str) -> str:
    """Extract iOS version from device model."""
    model_lower = model_name.lower()
    
    # iPhone versions
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
    elif 'iphone 7' in model_lower:
        return '10.0'
    elif 'iphone 6' in model_lower:
        return '9.0'
    elif 'se 3' in model_lower or 'se (3' in model_lower:
        return '15.0'
    elif 'se 2' in model_lower or 'se (2' in model_lower:
        return '13.0'
    
    # Watch versions
    elif 'watch series 11' in model_lower:
        return '11.0'
    elif 'watch series 10' in model_lower:
        return '10.0'
    elif 'watch series 9' in model_lower:
        return '10.0'
    elif 'watch series 8' in model_lower:
        return '9.0'
    elif 'watch series 7' in model_lower:
        return '8.0'
    elif 'watch series 6' in model_lower:
        return '7.0'
    elif 'watch series 5' in model_lower:
        return '6.0'
    elif 'watch series 4' in model_lower:
        return '5.0'
    elif 'watch ultra 3' in model_lower:
        return '11.0'
    elif 'watch ultra' in model_lower:
        return '9.0'
    elif 'watch se 3' in model_lower:
        return '10.0'
    elif 'watch se' in model_lower:
        return '7.0'
    elif 'watch hermes' in model_lower or 'watch nike' in model_lower:
        return '7.0'
    
    # iPad and iPod
    elif 'ipad' in model_lower:
        return '15.0'
    elif 'ipod' in model_lower:
        return '12.0'
    
    return '12.0'


def extract_android_version(model_name: str) -> str:
    """Extract Android version from device model."""
    model_lower = model_name.lower()
    
    # Google Pixel
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
    
    # Samsung S series
    elif 's25' in model_lower or 's24' in model_lower:
        return '14.0'
    elif 's23' in model_lower or 's22' in model_lower:
        return '13.0'
    elif 's21' in model_lower or 's20' in model_lower:
        return '11.0'
    elif 's10' in model_lower or 's9' in model_lower:
        return '10.0'
    
    # Year indicators
    elif '2025' in model_lower:
        return '15.0'
    elif '2024' in model_lower:
        return '14.0'
    elif '2023' in model_lower:
        return '13.0'
    elif '2022' in model_lower:
        return '12.0'
    elif '2021' in model_lower:
        return '11.0'
    
    # Samsung A series
    elif re.search(r'a5[456]', model_lower):
        return '14.0'
    elif re.search(r'a[23456]', model_lower):
        return '12.0'
    
    # OnePlus
    elif 'oneplus 13' in model_lower or 'oneplus 12' in model_lower:
        return '14.0'
    
    return '10.0'


if __name__ == '__main__':
    pdf_file = 'pdf/compatibility.pdf' if len(sys.argv) < 2 else sys.argv[1]
    
    try:
        parse_eversense_pdf(pdf_file)
        print("\n✅ PDF parsing completed successfully!")
        sys.exit(0)
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("📁 Expected location: pdf/compatibility.pdf")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error parsing PDF: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
