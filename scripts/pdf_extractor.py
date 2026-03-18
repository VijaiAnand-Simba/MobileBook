#!/usr/bin/env python3
"""
Text-based PDF extractor - doesn't rely on table structure.
"""

import pdfplumber
import re
import os
from datetime import datetime
from typing import Dict, List, Any
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
    """Text-based PDF extractor."""
    
    def __init__(self, pdf_path: str, region: str = "US"):
        self.pdf_path = pdf_path
        self.region = region
        
        self.KNOWN_MANUFACTURERS = [
            'Google', 'Samsung', 'OnePlus', 'Motorola', 'LG', 'HTC', 
            'Nokia', 'HMD Global', 'Sony', 'Xiaomi', 'Oppo', 'Vivo', 
            'Realme', 'Lively', 'TCL', 'Asus', 'Alcatel', 'Huawei', 'ZTE',
            'Apple'
        ]
    
    def extract(self) -> ExtractionResult:
        """Extract devices from PDF using text parsing."""
        
        print(f"\n{'='*70}")
        print(f"🔍 EXTRACTING: {os.path.basename(self.pdf_path)} ({self.region})")
        print(f"{'='*70}")
        
        devices = []
        errors = []
        tables_found = 0
        
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                current_table = None
                in_table = False
                
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if not text:
                        continue
                    
                    lines = text.split('\n')
                    
                    for line in lines:
                        line = line.strip()
                        
                        if not line:
                            continue
                        
                        # Detect table headers
                        table_match = self._detect_table(line)
                        if table_match:
                            current_table = table_match
                            in_table = False
                            tables_found += 1
                            print(f"\n📋 Page {page_num}: Table {table_match['num']} - {table_match['product']} {table_match['os'].upper()}")
                            continue
                        
                        # Skip until we find column headers
                        if current_table and not in_table:
                            if 'Device Manufacturer' in line or 'Manufacturer' in line:
                                in_table = True
                                print(f"   ✓ Found header row")
                                continue
                        
                        # Parse device lines
                        if current_table and in_table:
                            device = self._parse_device_line(
                                line, 
                                current_table['product'], 
                                current_table['os']
                            )
                            
                            if device:
                                devices.append(device)
            
            print(f"\n✅ Total: {len(devices)} devices from {tables_found} tables")
            
            return ExtractionResult(
                success=len(devices) > 0,
                method="text_parsing",
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
    
    
    def _detect_table(self, line: str) -> Dict:
        """Detect which table this line represents."""
        
        table_patterns = [
            (r'Table\s+3.*E3.*iOS', {"num": 3, "product": "E3", "os": "ios"}),
            (r'Table\s+4.*E3.*Android', {"num": 4, "product": "E3", "os": "android"}),
            (r'Table\s+5.*365.*iOS', {"num": 5, "product": "365", "os": "ios"}),
            (r'Table\s+6.*365.*Android', {"num": 6, "product": "365", "os": "android"}),
            (r'Table\s+7.*iOS.*NOW', {"num": 7, "product": "NOW", "os": "ios"}),
            (r'Table\s+7.*NOW.*iOS', {"num": 7, "product": "NOW", "os": "ios"}),
            (r'Table\s+8.*Android.*NOW', {"num": 8, "product": "NOW", "os": "android"}),
            (r'Table\s+8.*NOW.*Android', {"num": 8, "product": "NOW", "os": "android"}),
        ]
        
        for pattern, info in table_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return info
        
        return None
    
    
    def _parse_device_line(self, line: str, product: str, os_type: str) -> Dict:
        """Parse a device line from text."""
        
        # Skip header lines, page numbers, etc.
        if any(skip in line.lower() for skip in [
            'table ', 'page ', 'confidential', 'eversense', 
            'device manufacturer', 'model number', 'rationally qualified'
        ]):
            # Exception: actual device lines might contain "Confidential" in data
            if not any(mfr in line for mfr in self.KNOWN_MANUFACTURERS):
                return None
        
        # Check if line starts with a known manufacturer
        manufacturer = None
        for mfr in self.KNOWN_MANUFACTURERS:
            if line.startswith(mfr + ' ') or line.startswith(mfr + '\t'):
                manufacturer = mfr
                break
        
        if not manufacturer:
            return None
        
        # Remove manufacturer from line
        remaining = line[len(manufacturer):].strip()
        
        # Split by multiple spaces or tabs (columns)
        parts = re.split(r'\s{2,}|\t+', remaining)
        parts = [p.strip() for p in parts if p.strip()]
        
        if len(parts) < 1:
            return None
        
        model = parts[0]
        
        # Skip if model is empty or looks like metadata
        if not model or len(model) < 2:
            return None
        
        # Parse based on OS type
        if os_type == 'ios':
            # iOS format: Manufacturer, Model, Model Number
            # Apple iPhone 14    A2882
            
            if manufacturer != 'Apple':
                return None
            
            model_number = parts[1] if len(parts) > 1 else ''
            
            # Check if model_number is actually RQ status
            rq = False
            if 'rationally' in model_number.lower() or model_number.lower() == 'yes':
                rq = True
                model_number = ''
            
            # Extract iPhone models
            iphone_models = self._extract_iphone_models(model)
            
            if not iphone_models:
                return None
            
            # Return first model (can extend to return multiple)
            model = iphone_models[0]
            
            return {
                "name": f"Apple {model}",
                "manufacturer": "Apple",
                "model": model,
                "model_number": model_number,
                "os_version": self._get_ios_version(model),
                "rationally_qualified": rq or product == "NOW",
                "product": product,
                "region": self.region
            }
        
        else:
            # Android format: Manufacturer, Model Name, Model Number (Reference), RQ
            # Google    Pixel 5    Pixel 5    No (GD1YQ)
            # or: Google    Pixel 6    Pixel 6    Yes
            
            model_number = ''
            rq = False
            
            # Check last part for RQ status
            if len(parts) > 1:
                last_part = parts[-1]
                
                if last_part.lower() == 'yes':
                    rq = True
                elif 'no (' in last_part.lower():
                    # Extract model number from "No (GD1YQ)"
                    match = re.search(r'No\s*\(([^)]+)\)', last_part, re.IGNORECASE)
                    if match:
                        model_number = match.group(1)
                elif len(parts) > 2:
                    # Might be: Model, ModelNumber, RQ
                    model_number = parts[1] if parts[1] != model else ''
            
            return {
                "name": f"{manufacturer} {model}",
                "manufacturer": manufacturer,
                "model": model,
                "model_number": model_number,
                "os_version": self._get_android_version(model),
                "rationally_qualified": rq,
                "product": product,
                "region": self.region
            }
    
    
    def _extract_iphone_models(self, text: str) -> List[str]:
        """Extract iPhone model names."""
        pattern = r'iPhone\s+(?:\d+\s*(?:Pro\s*(?:Max)?|Plus|Mini)?|SE|X[RS]?(?:\s+Max)?)'
        
        matches = re.finditer(pattern, text, re.IGNORECASE)
        models = []
        
        for match in matches:
            model = match.group(0).strip()
            model = ' '.join(model.split())
            
            if model not in models:
                models.append(model)
        
        return models if models else [text]
    
    
    def _get_ios_version(self, model: str) -> str:
        """Get iOS version."""
        m = model.lower()
        
        if 'iphone 16' in m: return '18.0'
        if 'iphone 15' in m: return '17.0'
        if 'iphone 14' in m: return '16.0'
        if 'iphone 13' in m: return '15.0'
        if 'iphone 12' in m: return '14.0'
        if 'iphone 11' in m: return '13.0'
        if 'iphone x' in m: return '12.0'
        if 'iphone 8' in m: return '11.0'
        
        return '12.0'
    
    
    def _get_android_version(self, model: str) -> str:
        """Get Android version."""
        m = model.lower()
        
        if 'pixel 9' in m or 'pixel 8' in m: return '14.0'
        if 'pixel 7' in m or 'pixel 6' in m or 'pixel 5' in m: return '13.0'
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
