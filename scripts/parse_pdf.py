#!/usr/bin/env python3
"""
Parse Eversense compatibility PDF using proper table extraction.
Handles different column structures for iOS (3 cols) and Android (4 cols).
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
    
    # Table mapping
    table_configs = {
        3: {"product": "E3", "os": "ios", "columns": 3},
        4: {"product": "E3", "os": "android", "columns": 4},
        5: {"product": "365", "os": "ios", "columns": 3},
        6: {"product": "365", "os": "android", "columns": 4},
        7: {"product": "NOW", "os": "ios", "columns": 3},
        8: {"product": "NOW", "os": "android", "columns": 4}
    }
    
    current_table_num = None
    current_config = None
    in_table = False
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"📑 Total pages: {len(pdf.pages)}\n")
        
        for page_num, page in enumerate(pdf.pages, 1):
            # Extract text to find table markers
            text = page.extract_text()
            if not text:
                continue
            
            # Extract document metadata
            if 'Revision:' in text:
                revision_match = re.search(r'Revision:\s*(\d+)', text)
                if revision_match:
                    compatibility_data["document_info"]["revision"] = revision_match.group(1)
            
            if 'Effective Date:' in text:
                date_match = re.search(r'Effective Date:\s*(\d{1,2}\s+\w+\s+\d{4})', text)
                if date_match:
                    compatibility_data["document_info"]["effective_date"] = date_match.group(1).strip()
            
            # Detect table start
            for table_num, config in table_configs.items():
                pattern = f"Table {table_num}"
                if pattern in text:
                    current_table_num = table_num
                    current_config = config
                    in_table = True
                    print(f"{'📱' if config['os'] == 'ios' else '🤖'} Found Table {table_num} - {config['product']} {config['os'].upper()} (Page {page_num})")
                    break
            
            # Extract tables from page
            if in_table and current_config:
                tables = page.extract_tables()
                
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    
                    # Process table rows
                    devices_found = parse_table(table, current_config)
                    
                    if devices_found:
                        product = current_config['product']
                        os_type = current_config['os']
                        
                        for device in devices_found:
                            # Avoid duplicates
                            existing_names = [d['name'] for d in compatibility_data["products"][product][os_type]]
                            if device['name'] not in existing_names:
                                compatibility_data["products"][product][os_type].append(device)
            
            # Check if we've moved to next table
            next_table_text = f"Table {current_table_num + 1}" if current_table_num else None
            if next_table_text and next_table_text in text:
                if current_config:
                    product = current_config['product']
                    os_type = current_config['os']
                    count = len(compatibility_data["products"][product][os_type])
                    print(f"   ✅ Collected {count} devices\n")
                in_table = False
    
    # Final counts
    for table_num, config in table_configs.items():
        product = config['product']
        os_type = config['os']
        count = len(compatibility_data["products"][product][os_type])
        if count > 0:
            print(f"Table {table_num} ({config['product']} {config['os'].upper()}): {count} devices")
    
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


def parse_table(table: List[List[str]], config: Dict) -> List[Dict[str, Any]]:
    """Parse a table based on its configuration."""
    
    devices = []
    os_type = config['os']
    product = config['product']
    expected_cols = config['columns']
    
    # Skip header row(s)
    data_rows = []
    for row in table:
        # Clean the row
        cleaned_row = [cell.strip() if cell else '' for cell in row]
        
        # Skip empty rows
        if not any(cleaned_row):
            continue
        
        # Skip header rows
        if any(header in ' '.join(cleaned_row).lower() for header in ['device manufacturer', 'device model', 'model number', 'rationally qualified']):
            continue
        
        # Skip rows with confidential markers
        if any(skip in ' '.join(cleaned_row) for skip in ['Confidential', 'Property of Senseonics', 'Document #']):
            continue
        
        data_rows.append(cleaned_row)
    
    # Parse each data row
    for row in data_rows:
        if os_type == 'ios':
            device = parse_ios_row(row, product)
        else:
            device = parse_android_row(row, product)
        
        if device:
            devices.append(device)
    
    return devices


def parse_ios_row(row: List[str], product: str) -> Optional[Dict[str, Any]]:
    """
    Parse iOS table row (3 columns).
    Format: Device Manufacturer | Device Model | Model Number
    """
    
    if len(row) < 2:
        return None
    
    manufacturer = row[0].strip() if len(row) > 0 else ''
    device_model = row[1].strip() if len(row) > 1 else ''
    model_number = row[2].strip() if len(row) > 2 else ''
    
    # Skip if no manufacturer or model
    if not manufacturer or not device_model:
        return None
    
    # Skip if manufacturer is not Apple
    if 'apple' not in manufacturer.lower():
        return None
    
    # Clean up device model (remove size info like "(40 mm)")
    device_model_clean = re.sub(r'\s*\([^)]*\)', '', device_model).strip()
    
    # Create full device name
    device_name = f"{manufacturer} {device_model_clean}"
    
    # Determine if rationally qualified
    rationally_qualified = (
        'rationally qualified' in model_number.lower() or
        'rationally qualified' in device_model.lower()
    )
    
    # Extract iOS version
    os_version = extract_ios_version(device_model_clean)
    
    return {
        "name": device_name,
        "manufacturer": manufacturer,
        "model": device_model_clean,
        "model_number": model_number if model_number and model_number != 'Rationally Qualified' else '',
        "os_version": os_version,
        "rationally_qualified": rationally_qualified,
        "product": product
    }


def parse_android_row(row: List[str], product: str) -> Optional[Dict[str, Any]]:
    """
    Parse Android table row (4 columns).
    Format: Device Manufacturer | Device Model Name | Device Model Number (Reference) | Rationally qualified
    """
    
    if len(row) < 2:
        return None
    
    manufacturer = row[0].strip() if len(row) > 0 else ''
    model_name = row[1].strip() if len(row) > 1 else ''
    model_number_ref = row[2].strip() if len(row) > 2 else ''
    rationally_qualified_text = row[3].strip() if len(row) > 3 else ''
    
    # Skip if no manufacturer or model name
    if not manufacturer or not model_name:
        return None
    
    # Create full device name
    device_name = f"{manufacturer} {model_name}"
    
    # Parse model number
    # Sometimes it's just the model name repeated, sometimes it's "No (XXXXX)" or "Yes"
    model_number = ''
    if model_number_ref and model_number_ref.lower() != model_name.lower():
        # Extract from "No (XXX)" or "Yes" format
        no_match = re.search(r'No\s*\(([^)]+)\)', model_number_ref)
        if no_match:
            model_number = no_match.group(1)
        elif model_number_ref not in ['Yes', 'No']:
            model_number = model_number_ref
    
    # Determine if rationally qualified
    rationally_qualified = (
        rationally_qualified_text.lower() == 'yes' or
        'yes' in model_number_ref.lower()
    )
    
    # Extract Android version
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
    """Extract or infer iOS version from device model."""
    
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
    elif 'iphone xs' in model_lower or 'iphone xr' in model_lower or 'iphone x ' in model_lower:
        return '12.0'
    elif 'iphone 8' in model_lower:
        return '11.0'
    elif 'iphone 7' in model_lower:
        return '10.0'
    elif 'iphone 6' in model_lower:
        return '9.0'
    elif 'iphone se 3' in model_lower or 'se 3rd' in model_lower:
        return '15.0'
    elif 'iphone se 2' in model_lower or 'se 2nd' in model_lower:
        return '13.0'
    
    # Watch versions
    elif 'watch series 11' in model_lower or 'watch series11' in model_lower:
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
    
    # iPad and iPod
    elif 'ipad' in model_lower:
        return '15.0'
    elif 'ipod' in model_lower:
        return '12.0'
    
    return '12.0'


def extract_android_version(model_name: str) -> str:
    """Extract or infer Android version from device model."""
    
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
    elif 'pixel' in model_lower:
        return '10.0'
    
    # Samsung Galaxy S series
    elif 's25' in model_lower or 's24' in model_lower:
        return '14.0'
    elif 's23' in model_lower or 's22' in model_lower:
        return '13.0'
    elif 's21' in model_lower or 's20' in model_lower:
        return '11.0'
    elif 's10' in model_lower or 's9' in model_lower:
        return '10.0'
    
    # Samsung Galaxy A series (year-based)
    elif 'a56' in model_lower or 'a55' in model_lower or 'a54' in model_lower:
        return '14.0'
    elif 'a5' in model_lower or 'a3' in model_lower or 'a2' in model_lower:
        return '12.0'
    
    # Samsung Note series
    elif 'note20' in model_lower or 'note 20' in model_lower:
        return '11.0'
    elif 'note10' in model_lower or 'note 10' in model_lower:
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
    
    # OnePlus
    elif 'oneplus 13' in model_lower or 'oneplus 12' in model_lower:
        return '14.0'
    elif 'oneplus' in model_lower:
        return '12.0'
    
    # Motorola with years
    elif 'edge 2025' in model_lower or 'g 2025' in model_lower:
        return '15.0'
    elif 'edge 2024' in model_lower or 'g 2024' in model_lower:
        return '14.0'
    elif 'motorola' in model_lower:
        return '12.0'
    
    # Default
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
