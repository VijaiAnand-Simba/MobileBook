#!/usr/bin/env python3
"""
Parse Eversense compatibility PDF with ALL 6 tables.
Tables 3-8 covering E3, 365, and NOW application.
"""

import pdfplumber
import json
import re
from datetime import datetime
from typing import Dict, List, Any
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
    
    current_table = None
    table_started = False
    
    # Table mapping
    table_map = {
        "Table 3": ("E3", "ios"),        # E3 iOS MMA
        "Table 4": ("E3", "android"),    # E3 Android MMA
        "Table 5": ("365", "ios"),       # 365 iOS MMA
        "Table 6": ("365", "android"),   # 365 Android MMA
        "Table 7": ("NOW", "ios"),       # NOW iOS Application
        "Table 8": ("NOW", "android")    # NOW Android Application
    }
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"📑 Total pages: {len(pdf.pages)}")
        
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if not text:
                continue
            
            lines = text.split('\n')
            
            for line in lines:
                line = line.strip()
                
                # Extract document metadata
                if 'Revision:' in line:
                    revision_match = re.search(r'Revision:\s*(\d+)', line)
                    if revision_match:
                        compatibility_data["document_info"]["revision"] = revision_match.group(1)
                
                if 'Effective Date:' in line:
                    date_match = re.search(r'Effective Date:\s*(.+?)(?:Pages|$)', line)
                    if date_match:
                        compatibility_data["document_info"]["effective_date"] = date_match.group(1).strip()
                
                # Detect ALL 6 tables
                table_detected = False
                for table_key, (product, os_type) in table_map.items():
                    if table_key in line:
                        current_table = (product, os_type)
                        table_started = True
                        print(f"\n{'📱' if os_type == 'ios' else '🤖'} Found {table_key} - {product} {os_type.upper()} (Page {page_num})")
                        table_detected = True
                        break
                
                if table_detected:
                    continue
                
                # Skip table headers
                if table_started and ('Device Manufacturer' in line or 'Device Model' in line):
                    continue
                
                # End of table detection
                if table_started and line.startswith('Table') and current_table:
                    product, os_type = current_table
                    count = len(compatibility_data["products"][product][os_type])
                    print(f"   ✅ Parsed {count} devices")
                    table_started = False
                    continue
                
                # Parse device entries
                if table_started and current_table and line:
                    device_info = parse_device_line(line, current_table)
                    if device_info:
                        product, os_type = current_table
                        
                        # Avoid duplicates
                        existing_devices = [d['name'] for d in compatibility_data["products"][product][os_type]]
                        if device_info['name'] not in existing_devices:
                            compatibility_data["products"][product][os_type].append(device_info)
    
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
    print(f"📊 GRAND TOTAL: {total_devices} devices across all products")
    print(f"💾 Saved to: {output_file}")
    
    return compatibility_data


def parse_device_line(line: str, current_table: tuple) -> Dict[str, Any]:
    """Parse a single device line from the PDF."""
    
    # Skip confidential headers
    skip_keywords = [
        'Confidential', 'Document #', 'Property of', 'Title:', 'Pages:', 
        'The use of this', 'Effective Date', 'processor is not',
        'Revision:', 'Property of Senseonics'
    ]
    if any(keyword in line for keyword in skip_keywords):
        return None
    
    product, os_type = current_table
    
    # Clean the line
    line = re.sub(r'\s+', ' ', line).strip()
    
    if len(line) < 3:
        return None
    
    device_info = None
    
    if os_type == 'ios':
        device_info = parse_ios_device(line)
    else:
        device_info = parse_android_device(line)
    
    if device_info:
        device_info['product'] = product  # Add product line info
    
    return device_info


def parse_ios_device(line: str) -> Dict[str, Any]:
    """Parse iOS device line."""
    
    # Match Apple devices
    apple_match = re.match(r'Apple\s+(.+?)\s+([A-Z0-9]+(?:LL/A)?|Rationally Qualified|MEPJ4LW/A|MG464LL/A|MG184LL/A|MNHA3LL/A|MMX53LL/A|MX9M2LL/A|MTLV3LL/A|AA2848|A3082|A2481|A2111|A2172|A2783)', line, re.IGNORECASE)
    
    if apple_match:
        model_name = apple_match.group(1).strip()
        model_number = apple_match.group(2).strip()
        
        # Clean up model name
        model_name = re.sub(r'\s*\(.*?\)', '', model_name)
        
        os_version = extract_ios_version(model_name)
        
        return {
            "name": f"Apple {model_name}",
            "manufacturer": "Apple",
            "model": model_name,
            "model_number": model_number,
            "os_version": os_version,
            "rationally_qualified": model_number == "Rationally Qualified" or "Rationally qualified" in line
        }
    
    return None


def parse_android_device(line: str) -> Dict[str, Any]:
    """Parse Android device line."""
    
    manufacturers = [
        'Google', 'Samsung', 'OnePlus', 'Motorola', 'LG', 'HTC', 'Nokia', 
        'HMD Global', 'Lively', 'TCL', 'Xiaomi', 'Sony', 'Huawei', 'Oppo'
    ]
    
    for manufacturer in manufacturers:
        if line.startswith(manufacturer):
            remaining = line[len(manufacturer):].strip()
            
            # Split by multiple spaces or tabs
            parts = re.split(r'\s{2,}|\t', remaining)
            
            if len(parts) >= 1:
                model_name = parts[0].strip()
                model_number = parts[1].strip() if len(parts) > 1 else ""
                
                # Check rationally qualified
                rationally_qualified_text = parts[2] if len(parts) > 2 else ""
                rationally_qualified = 'Yes' in rationally_qualified_text
                
                # Extract model number from "No (XXX)" format
                model_match = re.search(r'\(([^)]+)\)', model_number)
                if model_match:
                    model_number = model_match.group(1)
                elif model_number in ['Yes', 'No']:
                    model_number = ""
                
                os_version = extract_android_version(model_name)
                
                return {
                    "name": f"{manufacturer} {model_name}",
                    "manufacturer": manufacturer,
                    "model": model_name,
                    "model_number": model_number,
                    "os_version": os_version,
                    "rationally_qualified": rationally_qualified
                }
    
    return None


def extract_ios_version(model_name: str) -> str:
    """Extract or infer iOS version from device model."""
    
    version_map = {
        'iPhone 17': '19.0',
        'iPhone 16': '18.0',
        'iPhone 15': '17.0',
        'iPhone 14': '16.0',
        'iPhone 13': '15.0',
        'iPhone 12': '14.0',
        'iPhone 11': '13.0',
        'iPhone X': '11.0',
        'iPhone 8': '11.0',
        'iPhone 7': '10.0',
        'iPhone 6': '8.0',
        'iPhone SE 3': '15.0',
        'iPhone SE 2': '13.0',
        'Watch Series 11': '11.0',
        'Watch Series 10': '10.0',
        'Watch Series 8': '9.0',
        'Watch Series 7': '8.0',
        'Watch Series 6': '7.0',
        'Watch Series 5': '6.0',
        'Watch Series 4': '5.0',
        'Watch Ultra': '9.0',
        'Watch SE': '7.0',
        'iPad': '15.0',
        'iPod': '12.0'
    }
    
    for key, version in version_map.items():
        if key.lower() in model_name.lower():
            return version
    
    return '12.0'


def extract_android_version(model_name: str) -> str:
    """Extract or infer Android version from device model."""
    
    if any(x in model_name for x in ['Pixel 10', 'Pixel 9']):
        return '14.0'
    elif 'Pixel 8' in model_name:
        return '14.0'
    elif 'Pixel 7' in model_name:
        return '13.0'
    elif 'Pixel 6' in model_name:
        return '12.0'
    elif any(year in model_name for year in ['2025', '2024']):
        return '14.0'
    elif '2023' in model_name:
        return '13.0'
    elif '2022' in model_name:
        return '12.0'
    
    # Samsung S series
    if 'S25' in model_name or 'S24' in model_name:
        return '14.0'
    elif 'S23' in model_name or 'S22' in model_name:
        return '13.0'
    
    return '10.0'


if __name__ == '__main__':
    pdf_file = 'pdf/compatibility.pdf' if len(sys.argv) < 2 else sys.argv[1]
    
    try:
        parse_eversense_pdf(pdf_file)
        print("\n✅ PDF parsing completed successfully!")
        sys.exit(0)
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error parsing PDF: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
