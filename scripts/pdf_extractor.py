#!/usr/bin/env python3
"""
Simple PDF extractor focused on exact table structures.
"""

import pdfplumber
import re
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import json


@dataclass
class ExtractionResult:
    success: bool
    method: str
    devices: List[Dict[str, Any]]
    tables_found: int
    confidence: float
    errors: List[str]


class UniversalPDFExtractor:
    """Simple PDF extractor for device tables."""
    
    def __init__(self, pdf_path: str, region: str = "US"):
        self.pdf_path = pdf_path
        self.region = region
        
        self.KNOWN_MANUFACTURERS = [
            'Google', 'Samsung', 'OnePlus', 'Motorola', 'LG', 'HTC', 
            'Nokia', 'HMD Global', 'Sony', 'Xiaomi', 'Oppo', 'Vivo', 
            'Realme', 'Lively', 'TCL', 'Asus', 'Alcatel', 'Huawei', 'ZTE'
        ]
    
    def extract(self) -> ExtractionResult:
        """Extract devices from PDF."""
        
        print(f"\n{'='*70}")
        print(f"🔍 EXTRACTING: {os.path.basename(self.pdf_path)} ({self.region})")
        print(f"{'='*70}")
        
        devices = []
        errors = []
        tables_found = 0
        
        # Table mapping: Table Number -> (Product, OS)
        table_map = {
            3: ("E3", "ios"),
            4: ("E3", "android"),
            5: ("365", "ios"),
            6: ("365", "android"),
            7: ("NOW", "ios"),
            8: ("NOW", "android"),
        }
        
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Get page text to find table markers
                    page_text = page.extract_text()
                    if not page_text:
                        continue
                    
                    # Extract tables from page
                    tables = page.extract_tables()
                    if not tables:
                        continue
                    
                    print(f"\n📄 Page {page_num}: {len(tables)} table(s)")
                    
                    # Find which table number is on this page
                    current_table_info = None
                    for table_num, (product, os_type) in table_map.items():
                        if f"Table {table_num}" in page_text or f"Table\n{table_num}" in page_text:
                            current_table_info = (product, os_type, table_num)
                            print(f"   Found: Table {table_num} - {product} {os_type.upper()}")
                            break
                    
                    # Process each table on the page
                    for table_idx, table in enumerate(tables):
                        if not table or len(table) < 2:
                            continue
                        
                        # Check if this is a device table
                        if table[0]:
                            header_text = ' '.join([str(c) for c in table[0] if c]).lower()
                            
                            if 'device manufacturer' not in header_text:
                                continue  # Not a device table
                        
                        # Use table info if found
                        if current_table_info:
                            product, os_type, table_num = current_table_info
                            
                            print(f"   📋 Parsing Table {table_num}: {len(table)} rows")
                            
                            parsed = self._parse_device_table(table, product, os_type)
                            devices.extend(parsed)
                            tables_found += 1
                            
                            print(f"      ✅ Extracted {len(parsed)} devices")
            
            print(f"\n✅ Total: {len(devices)} devices from {tables_found} tables")
            
            return ExtractionResult(
                success=len(devices) > 0,
                method="pdfplumber_tables",
                devices=devices,
                tables_found=tables_found,
                confidence=0.9 if len(devices) > 0 else 0.0,
                errors=errors
            )
            
        except Exception as e:
            errors.append(str(e))
            import traceback
            traceback.print_exc()
            return ExtractionResult(False, "failed", [], 0, 0.0, errors)
    
    
    def _parse_device_table(self, table: List[List], product: str, os_type: str) -> List[Dict]:
        """Parse a device table based on product and OS type."""
        
        devices = []
        
        for i, row in enumerate(table):
            if i == 0:  # Skip header
                continue
            
            if not row or len(row) < 2:
                continue
            
            # Clean row
            row = [str(cell).strip() if cell else '' for cell in row]
            row = [c for c in row if c]
            
            if len(row) < 2:
                continue
            
            manufacturer = row[0]
            model = row[1] if len(row) > 1 else ''
            
            if not manufacturer or not model:
                continue
            
            # iOS tables: [Manufacturer, Model, Model Number]
            if os_type == 'ios':
                if manufacturer.lower() != 'apple':
                    continue
                
                # Handle concatenated Apple entries
                apple_count = manufacturer.count('Apple')
                
                if apple_count > 1:
                    # Multiple iPhones in one row
                    models = self._extract_iphone_models(model)
                else:
                    models = [model]
                
                for m in models:
                    m = m.strip()
                    
                    # Skip noise
                    if m.lower() in ['confidential', 'rationally', 'qualified', '']:
                        continue
                    
                    if len(m) < 3:
                        continue
                    
                    model_number = row[2] if len(row) > 2 else ''
                    rq = 'rationally' in model_number.lower() if model_number else False
                    
                    if rq:
                        model_number = ''
                    
                    device = {
                        "name": f"Apple {m}",
                        "manufacturer": "Apple",
                        "model": m,
                        "model_number": model_number,
                        "os_version": self._get_ios_version(m),
                        "rationally_qualified": rq or product == "NOW",
                        "product": product,
                        "region": self.region
                    }
                    
                    devices.append(device)
            
            # Android tables: [Manufacturer, Model Name, Model Number (Reference), RQ]
            else:
                if manufacturer not in self.KNOWN_MANUFACTURERS:
                    continue
                
                # Parse RQ status
                rq = False
                model_number = ''
                
                if len(row) > 2:
                    # Third column might be model number or RQ
                    third_col = row[2]
                    
                    if third_col.lower() == 'yes':
                        rq = True
                    elif 'no (' in third_col.lower():
                        # Extract model number: "No (GD1YQ)"
                        match = re.search(r'No\s*\(([^)]+)\)', third_col, re.IGNORECASE)
                        if match:
                            model_number = match.group(1)
                    else:
                        model_number = third_col
                
                if len(row) > 3:
                    # Fourth column is RQ status
                    fourth_col = row[3]
                    if fourth_col.lower() == 'yes':
                        rq = True
                
                device = {
                    "name": f"{manufacturer} {model}",
                    "manufacturer": manufacturer,
                    "model": model,
                    "model_number": model_number,
                    "os_version": self._get_android_version(model),
                    "rationally_qualified": rq,
                    "product": product,
                    "region": self.region
                }
                
                devices.append(device)
        
        return devices
    
    
    def _extract_iphone_models(self, text: str) -> List[str]:
        """Extract iPhone model names from text."""
        
        pattern = r'iPhone\s+(?:\d+\s*(?:Pro\s*(?:Max)?|Plus|Mini)?|SE|X[RS]?(?:\s+Max)?)'
        
        matches = re.finditer(pattern, text, re.IGNORECASE)
        models = []
        
        for match in matches:
            model = match.group(0).strip()
            model = ' '.join(model.split())  # Normalize spaces
            
            if model not in models and model.lower() not in ['confidential', 'rationally', 'qualified']:
                models.append(model)
        
        return models if models else [text]
    
    
    def _get_ios_version(self, model: str) -> str:
        """Get iOS version for model."""
        m = model.lower()
        
        if 'iphone 16' in m: return '18.0'
        if 'iphone 15' in m: return '17.0'
        if 'iphone 14' in m: return '16.0'
        if 'iphone 13' in m: return '15.0'
        if 'iphone 12' in m: return '14.0'
        if 'iphone 11' in m: return '13.0'
        if 'iphone x' in m: return '12.0'
        if 'iphone 8' in m: return '11.0'
        if 'watch' in m: return '9.0'
        
        return '12.0'
    
    
    def _get_android_version(self, model: str) -> str:
        """Get Android version for model."""
        m = model.lower()
        
        if 'pixel 9' in m or 'pixel 8' in m: return '14.0'
        if 'pixel 7' in m or 'pixel 6' in m: return '13.0'
        if 's25' in m or 's24' in m: return '15.0'
        
        return '10.0'


def parse_eversense_pdf(pdf_path: str, region: str = "US") -> Dict[str, Any]:
    """Parse PDF and return compatibility data."""
    
    extractor = UniversalPDFExtractor(pdf_path, region)
    result = extractor.extract()
    
    compatibility_data = {
        "region": region,
        "last_updated": datetime.now().isoformat(),
        "document_info": {
            "revision": None,
            "effective_date": None,
            "source_file": os.path.basename(pdf_path),
            "extraction_method": result.method,
            "confidence": result.confidence
        },
        "products": {
            "E3": {"android": [], "ios": []},
            "365": {"android": [], "ios": []},
            "NOW": {"android": [], "ios": []}
        }
    }
    
    # Organize devices
    for device in result.devices:
        product = device.get('product', 'E3')
        os_type = device.get('os', 'android')
        
        if product in compatibility_data["products"] and os_type in compatibility_data["products"][product]:
            # Check duplicates
            existing = [d['name'] for d in compatibility_data["products"][product][os_type]]
            if device['name'] not in existing:
                compatibility_data["products"][product][os_type].append(device)
    
    return compatibility_data
