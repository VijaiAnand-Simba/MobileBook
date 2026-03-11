import pdfplumber
import json
import re
from datetime import datetime
from typing import Dict, List, Any

def parse_eversense_pdf(pdf_path: str) -> Dict[str, Any]:
    """Parse the Eversense compatibility PDF and extract device information."""
    
    compatibility_data = {
        "last_updated": datetime.now().isoformat(),
        "document_info": {
            "revision": None,
            "effective_date": None
        },
        "android": {
            "E3": [],
            "365": []
        },
        "ios": {
            "E3": [],
            "365": []
        }
    }
    
    current_table = None
    table_started = False
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if not text:
                continue
                
            lines = text.split('\n')
            
            for i, line in enumerate(lines):
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
                
                # Detect table headers
                if 'Table 3' in line and 'Eversense E3 iOS' in line:
                    current_table = ('ios', 'E3')
                    table_started = True
                    continue
                    
                elif 'Table 4' in line and 'Eversense E3 Android' in line:
                    current_table = ('android', 'E3')
                    table_started = True
                    continue
                    
                elif 'Table 5' in line and 'Eversense 365 iOS' in line:
                    current_table = ('ios', '365')
                    table_started = True
                    continue
                    
                elif 'Table 6' in line and 'Eversense 365 Android' in line:
                    current_table = ('android', '365')
                    table_started = True
                    continue
                
                # Skip table headers
                if table_started and ('Device Manufacturer' in line or 'Device Model' in line):
                    continue
                
                # End of table detection (next table or end of section)
                if table_started and ('Table' in line and line.startswith('Table')):
                    table_started = False
                    current_table = None
                    continue
                
                # Parse device entries
                if table_started and current_table and line:
                    device_info = parse_device_line(line, current_table)
                    if device_info:
                        os_type, product_line = current_table
                        
                        # Avoid duplicates
                        existing_devices = [d['name'] for d in compatibility_data[os_type][product_line]]
                        if device_info['name'] not in existing_devices:
                            compatibility_data[os_type][product_line].append(device_info)
            
            # Also try table extraction for better accuracy
            tables = page.extract_tables()
            for table in tables:
                if table and len(table) > 1:
                    parse_table_structure(table, compatibility_data, current_table)
    
    # Save to JSON
    with open('data/compatibility.json', 'w', encoding='utf-8') as f:
        json.dump(compatibility_data, f, indent=2, ensure_ascii=False)
    
    total_devices = sum(
        len(devices) 
        for os_data in [compatibility_data['android'], compatibility_data['ios']]
        for devices in os_data.values()
    )
    
    print(f"✅ Parsed {total_devices} devices")
    print(f"   - iOS E3: {len(compatibility_data['ios']['E3'])}")
    print(f"   - iOS 365: {len(compatibility_data['ios']['365'])}")
    print(f"   - Android E3: {len(compatibility_data['android']['E3'])}")
    print(f"   - Android 365: {len(compatibility_data['android']['365'])}")
    
    return compatibility_data

def parse_device_line(line: str, current_table: tuple) -> Dict[str, Any]:
    """Parse a single device line from the PDF."""
    
    # Skip confidential headers and page markers
    skip_keywords = ['Confidential', 'Document #', 'Property of', 'Title:', 'Pages:', 
                     'The use of this', 'Effective Date', 'processor is not']
    if any(keyword in line for keyword in skip_keywords):
        return None
    
    os_type, product_line = current_table
    
    # Clean the line
    line = re.sub(r'\s+', ' ', line).strip()
    
    # Skip empty or very short lines
    if len(line) < 3:
        return None
    
    device_info = None
    
    if os_type == 'ios':
        # iOS format: Manufacturer | Model | Model Number
        device_info = parse_ios_device(line)
    else:
        # Android format: Manufacturer | Model Name | Model Number | Rationally Qualified
        device_info = parse_android_device(line)
    
    return device_info

def parse_ios_device(line: str) -> Dict[str, Any]:
    """Parse iOS device line."""
    
    # Common iOS manufacturers
    manufacturers = ['Apple']
    
    # Try to match Apple devices
    apple_match = re.match(r'Apple\s+(.+?)\s+([A-Z0-9]+(?:LL/A)?|Rationally Qualified)', line, re.IGNORECASE)
    if apple_match:
        model_name = apple_match.group(1).strip()
        model_number = apple_match.group(2).strip()
        
        # Extract OS version from model name if present
        os_version = extract_ios_version(model_name)
        
        return {
            "name": f"Apple {model_name}",
            "manufacturer": "Apple",
            "model": model_name,
            "model_number": model_number,
            "os_version": os_version,
            "rationally_qualified": model_number == "Rationally Qualified"
        }
    
    return None

def parse_android_device(line: str) -> Dict[str, Any]:
    """Parse Android device line."""
    
    # Android manufacturers
    manufacturers = ['Google', 'Samsung', 'OnePlus', 'Motorola', 'LG', 'HTC', 'Nokia', 
                    'HMD Global', 'Lively', 'TCL']
    
    for manufacturer in manufacturers:
        if line.startswith(manufacturer):
            # Remove manufacturer from line
            remaining = line[len(manufacturer):].strip()
            
            # Try to split by common patterns
            parts = re.split(r'\s{2,}|\t', remaining)
            
            if len(parts) >= 2:
                model_name = parts[0].strip()
                model_number = parts[1].strip() if len(parts) > 1 else ""
                rationally_qualified = "Yes" in line or "No" in line
                
                # Extract OS version
                os_version = extract_android_version(line)
                
                # Clean model number (remove "No (XXX)" or "Yes" text)
                model_number_clean = re.sub(r'(Yes|No)\s*\(([^)]+)\)', r'\2', model_number)
                if model_number_clean == "Yes" or model_number_clean == "No":
                    model_number_clean = parts[1].strip() if len(parts) > 1 else ""
                
                return {
                    "name": f"{manufacturer} {model_name}",
                    "manufacturer": manufacturer,
                    "model": model_name,
                    "model_number": model_number_clean,
                    "os_version": os_version,
                    "rationally_qualified": rationally_qualified
                }
    
    return None

def parse_table_structure(table: List[List[str]], compatibility_data: Dict, current_table: tuple):
    """Parse structured table data extracted by pdfplumber."""
    
    if not current_table or not table:
        return
    
    os_type, product_line = current_table
    
    # Skip header row
    for row in table[1:]:
        if not row or len(row) < 2:
            continue
        
        # Filter out None values and empty strings
        row = [cell.strip() if cell else '' for cell in row]
        
        if os_type == 'ios' and len(row) >= 2:
            manufacturer = row[0]
            model = row[1]
            model_number = row[2] if len(row) > 2 else ''
            
            if manufacturer and model and manufacturer not in ['Device Manufacturer', 'Confidential']:
                device_info = {
                    "name": f"{manufacturer} {model}",
                    "manufacturer": manufacturer,
                    "model": model,
                    "model_number": model_number,
                    "os_version": extract_ios_version(model),
                    "rationally_qualified": model_number == "Rationally Qualified"
                }
                
                # Check for duplicates
                existing = [d['name'] for d in compatibility_data[os_type][product_line]]
                if device_info['name'] not in existing:
                    compatibility_data[os_type][product_line].append(device_info)
        
        elif os_type == 'android' and len(row) >= 3:
            manufacturer = row[0]
            model_name = row[1]
            model_number = row[2] if len(row) > 2 else ''
            
            if manufacturer and model_name and manufacturer not in ['Device Manufacturer', 'Confidential']:
                device_info = {
                    "name": f"{manufacturer} {model_name}",
                    "manufacturer": manufacturer,
                    "model": model_name,
                    "model_number": model_number,
                    "os_version": extract_android_version(model_name),
                    "rationally_qualified": len(row) > 3 and 'Yes' in str(row[3])
                }
                
                # Check for duplicates
                existing = [d['name'] for d in compatibility_data[os_type][product_line]]
                if device_info['name'] not in existing:
                    compatibility_data[os_type][product_line].append(device_info)

def extract_ios_version(model_name: str) -> str:
    """Extract or infer iOS version from device model."""
    
    # iOS version mapping based on device model
    version_map = {
        'iPhone 6': '12.0',
        'iPhone 7': '15.0',
        'iPhone 8': '16.0',
        'iPhone X': '16.0',
        'iPhone 11': '17.0',
        'iPhone 12': '17.0',
        'iPhone 13': '17.0',
        'iPhone 14': '16.0',
        'iPhone 15': '17.0',
        'iPhone 16': '18.0',
        'iPhone 17': '18.0',
        'iPhone SE 2': '15.0',
        'iPhone SE 3': '16.0',
        'Watch Series': '5.0',
        'iPad': '15.0'
    }
    
    for key, version in version_map.items():
        if key.lower() in model_name.lower():
            return version
    
    return '12.0'  # Default minimum iOS version

def extract_android_version(model_name: str) -> str:
    """Extract or infer Android version from device model."""
    
    # Android version mapping (approximate based on release years)
    if 'Pixel 9' in model_name or 'Pixel 10' in model_name:
        return '14.0'
    elif 'Pixel 8' in model_name:
        return '14.0'
    elif 'Pixel 7' in model_name:
        return '13.0'
    elif 'Pixel 6' in model_name:
        return '12.0'
    elif any(year in model_name for year in ['2024', '2025']):
        return '13.0'
    elif '2023' in model_name:
        return '12.0'
    elif '2022' in model_name:
        return '11.0'
    
    return '9.0'  # Default minimum Android version from the document

if __name__ == '__main__':
    import sys
    
    pdf_file = 'compatibility.pdf' if len(sys.argv) < 2 else sys.argv[1]
    
    try:
        parse_eversense_pdf(pdf_file)
        print("\n✅ PDF parsing completed successfully!")
    except FileNotFoundError:
        print(f"❌ Error: PDF file '{pdf_file}' not found")
        print("Usage: python parse_pdf.py [path_to_pdf]")
    except Exception as e:
        print(f"❌ Error parsing PDF: {e}")
        import traceback
        traceback.print_exc()
