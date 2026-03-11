import pdfplumber
import json
import re
from datetime import datetime
from typing import Dict, List, Any
import sys
import os

def parse_eversense_pdf(pdf_path: str) -> Dict[str, Any]:
    """Parse the Eversense compatibility PDF and extract device information."""
    
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
        print(f"📑 Total pages: {len(pdf.pages)}")
        
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
                        print(f"📋 Document Revision: {revision_match.group(1)}")
                
                if 'Effective Date:' in line:
                    date_match = re.search(r'Effective Date:\s*(.+?)(?:Pages|$)', line)
                    if date_match:
                        compatibility_data["document_info"]["effective_date"] = date_match.group(1).strip()
                        print(f"📅 Effective Date: {date_match.group(1).strip()}")
                
                # Detect table headers
                if 'Table 3' in line and ('E3 iOS' in line or 'iOS MMA' in line):
                    current_table = ('ios', 'E3')
                    table_started = True
                    print(f"\n📱 Found Table 3 - iOS E3 (Page {page_num})")
                    continue
                    
                elif 'Table 4' in line and ('E3 Android' in line or 'Android MMA' in line):
                    current_table = ('android', 'E3')
                    table_started = True
                    print(f"\n🤖 Found Table 4 - Android E3 (Page {page_num})")
                    continue
                    
                elif 'Table 5' in line and ('365 iOS' in line or 'iOS MMA' in line):
                    current_table = ('ios', '365')
                    table_started = True
                    print(f"\n📱 Found Table 5 - iOS 365 (Page {page_num})")
                    continue
                    
                elif 'Table 6' in line and ('365 Android' in line or 'Android MMA' in line):
                    current_table = ('android', '365')
                    table_started = True
                    print(f"\n🤖 Found Table 6 - Android 365 (Page {page_num})")
                    continue
                
                # Skip table headers
                if table_started and ('Device Manufacturer' in line or 'Device Model' in line):
                    continue
                
                # End of table detection
                if table_started and line.startswith('Table') and current_table:
                    os_type, product = current_table
                    count = len(compatibility_data[os_type][product])
                    print(f"   ✅ Parsed {count} devices")
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
    
    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)
    
    # Save to JSON
    output_file = 'data/compatibility.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(compatibility_data, f, indent=2, ensure_ascii=False)
    
    total_devices = sum(
        len(devices) 
        for os_data in [compatibility_data['android'], compatibility_data['ios']]
        for devices in os_data.values()
    )
    
    print(f"\n{'='*50}")
    print(f"✅ PARSING COMPLETED")
    print(f"{'='*50}")
    print(f"📊 Total devices parsed: {total_devices}")
    print(f"   📱 iOS E3: {len(compatibility_data['ios']['E3'])} devices")
    print(f"   📱 iOS 365: {len(compatibility_data['ios']['365'])} devices")
    print(f"   🤖 Android E3: {len(compatibility_data['android']['E3'])} devices")
    print(f"   🤖 Android 365: {len(compatibility_data['android']['365'])} devices")
    print(f"\n💾 Saved to: {output_file}")
    
    return compatibility_data

def parse_device_line(line: str, current_table: tuple) -> Dict[str, Any]:
    """Parse a single device line from the PDF."""
    
    # Skip confidential headers and page markers
    skip_keywords = [
        'Confidential', 'Document #', 'Property of', 'Title:', 'Pages:', 
        'The use of this', 'Effective Date', 'processor is not',
        'Revision:', 'Property of Senseonics'
    ]
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
        device_info = parse_ios_device(line)
    else:
        device_info = parse_android_device(line)
    
    return device_info

def parse_ios_device(line: str) -> Dict[str, Any]:
    """Parse iOS device line."""
    
    # Try to match Apple devices
    # Format: Apple | Device Name | Model Number
    apple_match = re.match(r'Apple\s+(.+?)\s+([A-Z0-9]+(?:LL/A)?|Rationally Qualified|MEPJ4LW/A|MG464LL/A)', line, re.IGNORECASE)
    if apple_match:
        model_name = apple_match.group(1).strip()
        model_number = apple_match.group(2).strip()
        
        # Clean up model name (remove extra text)
        model_name = re.sub(r'\s*\(.*?\)', '', model_name)
        
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
    manufacturers = [
        'Google', 'Samsung', 'OnePlus', 'Motorola', 'LG', 'HTC', 'Nokia', 
        'HMD Global', 'Lively', 'TCL', 'Xiaomi', 'Huawei', 'OPPO', 'Vivo'
    ]
    
    for manufacturer in manufacturers:
        if line.startswith(manufacturer):
            # Remove manufacturer from line
            remaining = line[len(manufacturer):].strip()
            
            # Split by multiple spaces or tabs
            parts = re.split(r'\s{2,}|\t', remaining)
            
            if len(parts) >= 1:
                model_name = parts[0].strip()
                model_number = parts[1].strip() if len(parts) > 1 else ""
                
                # Check if rationally qualified
                rationally_qualified_text = parts[2] if len(parts) > 2 else ""
                rationally_qualified = 'Yes' in rationally_qualified_text
                
                # Extract model number from "No (XXX)" or "Yes" format
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
    
    # iOS version mapping based on device model
    version_map = {
        'iPhone 17': '18.0',
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
        'Watch Series 9': '10.0',
        'Watch Series 8': '9.0',
        'Watch Series 7': '8.0',
        'Watch Series 6': '7.0',
        'Watch Series 5': '6.0',
        'Watch Series 4': '5.0',
        'Watch Ultra': '9.0',
        'Watch SE': '7.0',
        'iPad Pro': '15.0',
        'iPad': '15.0',
        'iPod': '12.0'
    }
    
    for key, version in version_map.items():
        if key.lower() in model_name.lower():
            return version
    
    return '12.0'  # Default minimum iOS version

def extract_android_version(model_name: str) -> str:
    """Extract or infer Android version from device model."""
    
    # Android version mapping
    if any(x in model_name for x in ['Pixel 10', 'Pixel 9']):
        return '14.0'
    elif 'Pixel 8' in model_name:
        return '14.0'
    elif 'Pixel 7' in model_name:
        return '13.0'
    elif 'Pixel 6' in model_name:
        return '12.0'
    elif 'Pixel 5' in model_name or 'Pixel 4' in model_name:
        return '11.0'
    elif any(year in model_name for year in ['2025']):
        return '14.0'
    elif '2024' in model_name:
        return '13.0'
    elif '2023' in model_name:
        return '12.0'
    elif '2022' in model_name:
        return '11.0'
    elif '2021' in model_name:
        return '10.0'
    
    return '9.0'  # Default minimum Android version

if __name__ == '__main__':
    pdf_file = 'pdf/compatibility.pdf' if len(sys.argv) < 2 else sys.argv[1]
    
    try:
        parse_eversense_pdf(pdf_file)
        print("\n✅ PDF parsing completed successfully!")
        sys.exit(0)
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("📁 Expected location: pdf/compatibility.pdf")
        print("Usage: python scripts/parse_pdf.py [path_to_pdf]")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error parsing PDF: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
