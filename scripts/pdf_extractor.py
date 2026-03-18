#!/usr/bin/env python3
"""
Universal PDF extractor with multiple fallback strategies.
Handles text transformations, rotations, format changes, and concatenated devices.
"""

import pdfplumber
import fitz  # PyMuPDF
import pandas as pd
import re
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import json


@dataclass
class ExtractionResult:
    """Results from a PDF extraction attempt."""
    success: bool
    method: str
    devices: List[Dict[str, Any]]
    tables_found: int
    confidence: float
    errors: List[str]


class UniversalPDFExtractor:
    """Multi-strategy PDF extractor with automatic fallback."""
    
    def __init__(self, pdf_path: str, region: str = "US"):
        self.pdf_path = pdf_path
        self.region = region
        self.results = []
        
        # Known manufacturers for validation
        self.KNOWN_MANUFACTURERS = [
            'Google', 'Samsung', 'OnePlus', 'Motorola', 'LG', 'HTC', 
            'Nokia', 'HMD Global', 'Sony', 'Xiaomi', 'Oppo', 'Vivo', 
            'Realme', 'Lively', 'TCL', 'Asus', 'Alcatel', 'Huawei', 
            'ZTE', 'Lenovo', 'BlackBerry'
        ]
        
    def extract(self) -> ExtractionResult:
        """Try multiple extraction methods in order of reliability."""
        
        print(f"\n{'='*70}")
        print(f"🔍 EXTRACTING: {os.path.basename(self.pdf_path)} ({self.region})")
        print(f"{'='*70}")
        
        # Strategy 1: pdfplumber table extraction (most reliable for tables)
        result = self._try_pdfplumber_tables()
        if result.success and result.confidence > 0.7:
            print(f"✅ Method: {result.method} | Confidence: {result.confidence:.0%}")
            return result
        self.results.append(result)
        
        # Strategy 2: pdfplumber with layout analysis
        result = self._try_pdfplumber_layout()
        if result.success and result.confidence > 0.7:
            print(f"✅ Method: {result.method} | Confidence: {result.confidence:.0%}")
            return result
        self.results.append(result)
        
        # Strategy 3: PyMuPDF (handles transformations better)
        result = self._try_pymupdf()
        if result.success and result.confidence > 0.6:
            print(f"✅ Method: {result.method} | Confidence: {result.confidence:.0%}")
            return result
        self.results.append(result)
        
        # Return best result
        best = max(self.results, key=lambda r: r.confidence) if self.results else ExtractionResult(
            False, "none", [], 0, 0.0, ["No extraction methods succeeded"]
        )
        print(f"⚠️  Best available: {best.method} | Confidence: {best.confidence:.0%}")
        return best
    
    
    def _split_concatenated_models(self, text: str, manufacturer: str = "") -> List[str]:
        """
        Split concatenated device models intelligently.
        Handles: "Pixel 8, Pixel 9" or "Galaxy S23, Galaxy S24, Galaxy S25"
        """
        
        # Remove manufacturer prefix if present
        if manufacturer and text.startswith(manufacturer):
            text = text[len(manufacturer):].strip()
        
        # Split by common separators
        # Patterns: ", ", " and ", "; ", " & "
        models = re.split(r',\s*(?:and\s+)?|;\s*|\s+and\s+|\s+&\s+', text)
        
        cleaned_models = []
        for model in models:
            model = model.strip()
            
            # Remove leading conjunctions
            model = re.sub(r'^(and|or)\s+', '', model, flags=re.IGNORECASE).strip()
            
            # Remove trailing punctuation
            model = re.sub(r'[,;.]$', '', model).strip()
            
            # Skip if too short or empty
            if len(model) < 2:
                continue
            
            # Skip metadata/noise patterns
            skip_patterns = [
                r'^table\s+\d+',
                r'rationally\s+qualified',
                r'^see\s+',
                r'^note\s*:',
                r'^version\s+',
                r'^\d+\.\d+$',  # Just version numbers like "10.0"
                r'^page\s+\d+',
                r'^compatible',
                r'^mma\s+app',
            ]
            
            if any(re.search(pattern, model, re.IGNORECASE) for pattern in skip_patterns):
                continue
            
            cleaned_models.append(model)
        
        return cleaned_models if cleaned_models else [text]
    
    
    def _is_valid_manufacturer(self, manufacturer: str, os_type: str) -> bool:
        """Validate manufacturer for given OS type."""
        
        manufacturer = manufacturer.strip()
        
        # Apple only in iOS
        if manufacturer.lower() == 'apple':
            return os_type == 'ios'
        
        # Other manufacturers only in Android
        if manufacturer in self.KNOWN_MANUFACTURERS:
            return os_type == 'android'
        
        return False
    
    
    def _try_pdfplumber_tables(self) -> ExtractionResult:
        """Extract using pdfplumber's table detection."""
        
        print("\n📊 Trying: pdfplumber table extraction...")
        devices = []
        errors = []
        tables_found = 0
        
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Extract tables
                    tables = page.extract_tables()
                    
                    if not tables:
                        continue
                    
                    for table_idx, table in enumerate(tables):
                        if not table or len(table) < 2:
                            continue
                        
                        tables_found += 1
                        
                        # Identify table type from headers or nearby text
                        table_info = self._identify_table(page, table, page_num)
                        
                        if not table_info:
                            continue
                        
                        # Parse rows
                        parsed = self._parse_table_rows(
                            table, 
                            table_info['os'], 
                            table_info['product']
                        )
                        
                        devices.extend(parsed)
                        print(f"   Page {page_num}, Table {table_idx+1}: {len(parsed)} devices ({table_info['product']}/{table_info['os']})")
            
            confidence = self._calculate_confidence(devices, tables_found)
            
            return ExtractionResult(
                success=len(devices) > 0,
                method="pdfplumber_tables",
                devices=devices,
                tables_found=tables_found,
                confidence=confidence,
                errors=errors
            )
            
        except Exception as e:
            errors.append(str(e))
            return ExtractionResult(False, "pdfplumber_tables", [], 0, 0.0, errors)
    
    
    def _try_pdfplumber_layout(self) -> ExtractionResult:
        """Extract using pdfplumber with layout analysis."""
        
        print("\n📄 Trying: pdfplumber layout analysis...")
        devices = []
        errors = []
        
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                current_table = None
                header_seen = False
                
                for page_num, page in enumerate(pdf.pages, 1):
                    # Try to fix rotated/flipped text
                    text = page.extract_text()
                    
                    if not text:
                        continue
                    
                    lines = text.split('\n')
                    
                    for line in lines:
                        line = line.strip()
                        
                        if not line:
                            continue
                        
                        # Detect table headers
                        table_match = self._detect_table_header(line)
                        if table_match:
                            current_table = table_match
                            header_seen = False
                            continue
                        
                        # Detect column headers
                        if current_table and not header_seen:
                            if 'Device Manufacturer' in line or 'Manufacturer' in line:
                                header_seen = True
                                continue
                        
                        # Parse device lines (returns list now)
                        if current_table and header_seen:
                            parsed_devices = self._parse_device_line(
                                line,
                                current_table['os'],
                                current_table['product']
                            )
                            if parsed_devices:
                                devices.extend(parsed_devices)
            
            confidence = self._calculate_confidence(devices, len(devices))
            
            return ExtractionResult(
                success=len(devices) > 0,
                method="pdfplumber_layout",
                devices=devices,
                tables_found=len(set(d.get('product', '') + d.get('os', '') for d in devices)),
                confidence=confidence,
                errors=errors
            )
            
        except Exception as e:
            errors.append(str(e))
            return ExtractionResult(False, "pdfplumber_layout", [], 0, 0.0, errors)
    
    
    def _try_pymupdf(self) -> ExtractionResult:
        """Extract using PyMuPDF (better handles transformations)."""
        
        print("\n📑 Trying: PyMuPDF extraction...")
        devices = []
        errors = []
        
        try:
            doc = fitz.open(self.pdf_path)
            current_table = None
            header_seen = False
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Extract text with layout preservation
                text = page.get_text("text")
                
                if not text:
                    continue
                
                lines = text.split('\n')
                
                for line in lines:
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    # Detect table headers
                    table_match = self._detect_table_header(line)
                    if table_match:
                        current_table = table_match
                        header_seen = False
                        print(f"   Found: {current_table['product']} {current_table['os'].upper()} (Page {page_num+1})")
                        continue
                    
                    # Detect column headers
                    if current_table and not header_seen:
                        if 'Device Manufacturer' in line or 'Manufacturer' in line:
                            header_seen = True
                            continue
                    
                    # Parse device lines (returns list now)
                    if current_table and header_seen:
                        parsed_devices = self._parse_device_line(
                            line,
                            current_table['os'],
                            current_table['product']
                        )
                        if parsed_devices:
                            devices.extend(parsed_devices)
            
            doc.close()
            
            confidence = self._calculate_confidence(devices, len(devices))
            
            return ExtractionResult(
                success=len(devices) > 0,
                method="pymupdf",
                devices=devices,
                tables_found=len(set(d.get('product', '') + d.get('os', '') for d in devices)),
                confidence=confidence,
                errors=errors
            )
            
        except Exception as e:
            errors.append(str(e))
            return ExtractionResult(False, "pymupdf", [], 0, 0.0, errors)
    
    
    def _detect_table_header(self, line: str) -> Optional[Dict[str, str]]:
        """Detect table type from header line."""
        
        patterns = [
            (r'E3.*?iOS.*?(?:MMA|Compatible)', {"product": "E3", "os": "ios"}),
            (r'E3.*?Android.*?(?:MMA|Compatible)', {"product": "E3", "os": "android"}),
            (r'365.*?iOS.*?(?:MMA|Compatible)', {"product": "365", "os": "ios"}),
            (r'365.*?Android.*?(?:MMA|Compatible)', {"product": "365", "os": "android"}),
            (r'NOW.*?iOS.*?App', {"product": "NOW", "os": "ios"}),
            (r'NOW.*?Android.*?App', {"product": "NOW", "os": "android"}),
        ]
        
        for pattern, info in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return info
        
        return None
    
    
    def _identify_table(self, page, table: List[List], page_num: int) -> Optional[Dict[str, str]]:
        """Identify table type from nearby text or content."""
        
        # Check text above table
        text = page.extract_text()
        if text:
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if i > 20:  # Only check first 20 lines
                    break
                
                match = self._detect_table_header(line)
                if match:
                    return match
        
        # Check first row of table for clues
        if table and table[0]:
            first_row = ' '.join(str(cell) for cell in table[0] if cell)
            match = self._detect_table_header(first_row)
            if match:
                return match
        
        return None
    
    
    def _parse_table_rows(self, table: List[List], os_type: str, product: str) -> List[Dict]:
        """Parse table rows into device objects."""
        
        devices = []
        
        # Skip header row(s)
        for i, row in enumerate(table):
            if i == 0:
                continue  # Skip first row (usually header)
            
            if not row or all(cell is None or str(cell).strip() == '' for cell in row):
                continue  # Skip empty rows
            
            # Convert row to device(s) - now returns list
            row_devices = self._row_to_devices(row, os_type, product)
            if row_devices:
                devices.extend(row_devices)
        
        return devices
    
    
    def _row_to_devices(self, row: List, os_type: str, product: str) -> List[Dict]:
        """
        Convert table row to device object(s).
        Returns LIST because one row might contain multiple concatenated devices.
        """
        
        # Clean row
        row = [str(cell).strip() if cell is not None else '' for cell in row]
        row = [cell for cell in row if cell]  # Remove empty cells
        
        if len(row) < 2:
            return []
        
        manufacturer = row[0].strip()
        model_text = row[1].strip() if len(row) > 1 else ''
        
        if not model_text:
            return []
        
        # Validate manufacturer for OS type
        if not self._is_valid_manufacturer(manufacturer, os_type):
            return []
        
        devices = []
        
        if os_type == 'ios':
            # iOS: [Manufacturer, Model, Model Number]
            model_number = row[2] if len(row) > 2 else ''
            
            # Split concatenated models
            models = self._split_concatenated_models(model_text, manufacturer)
            
            for model in models:
                # Clean model
                model = re.sub(r'\s*\(\d+\s*mm\)', '', model).strip()
                
                if not model or len(model) < 2:
                    continue
                
                device = {
                    "name": f"Apple {model}",
                    "manufacturer": "Apple",
                    "model": model,
                    "model_number": model_number if 'Rationally' not in model_number else '',
                    "os_version": self._extract_ios_version(model),
                    "rationally_qualified": 'rationally qualified' in ' '.join(row).lower(),
                    "product": product,
                    "region": self.region
                }
                
                devices.append(device)
        
        else:
            # Android: [Manufacturer, Model, Model Number, RQ]
            
            # Extract RQ and model number from last columns
            rq = False
            model_number = ''
            
            if len(row) > 2:
                last_col = row[-1]
                if last_col.lower() == 'yes':
                    rq = True
                elif 'no (' in last_col.lower():
                    match = re.search(r'No\s*\(([^)]+)\)', last_col, re.IGNORECASE)
                    if match:
                        model_number = match.group(1)
                elif len(row) > 3:
                    # Model number might be in second-to-last column
                    model_number = row[-2] if row[-2] not in ['Yes', 'No'] else ''
                else:
                    model_number = last_col
            
            # Split concatenated models
            models = self._split_concatenated_models(model_text, manufacturer)
            
            for model in models:
                if not model or len(model) < 2:
                    continue
                
                device = {
                    "name": f"{manufacturer} {model}",
                    "manufacturer": manufacturer,
                    "model": model,
                    "model_number": model_number,
                    "os_version": self._extract_android_version(model),
                    "rationally_qualified": rq,
                    "product": product,
                    "region": self.region
                }
                
                devices.append(device)
        
        return devices
    
    
    def _parse_device_line(self, line: str, os_type: str, product: str) -> List[Dict]:
        """
        Parse a single device line (text-based).
        Returns LIST to handle concatenated devices.
        """
        
        if len(line) < 5:
            return []
        
        devices = []
        
        if os_type == 'ios':
            if not line.startswith('Apple'):
                return []
            
            remaining = line[5:].strip()
            parts = re.split(r'\s{2,}', remaining)
            
            if len(parts) < 1:
                return []
            
            model_text = parts[0].strip()
            model_number = parts[1].strip() if len(parts) > 1 else ''
            
            # Split concatenated models
            models = self._split_concatenated_models(model_text, 'Apple')
            
            for model in models:
                # Clean model
                model = re.sub(r'\s*\(\d+\s*mm\)', '', model).strip()
                
                if not model or len(model) < 2:
                    continue
                
                device = {
                    "name": f"Apple {model}",
                    "manufacturer": "Apple",
                    "model": model,
                    "model_number": model_number if 'Rationally' not in model_number else '',
                    "os_version": self._extract_ios_version(model),
                    "rationally_qualified": 'rationally qualified' in line.lower(),
                    "product": product,
                    "region": self.region
                }
                
                devices.append(device)
        
        else:
            # Android parsing
            manufacturer = None
            for mfr in self.KNOWN_MANUFACTURERS:
                if line.startswith(mfr):
                    manufacturer = mfr
                    break
            
            if not manufacturer:
                return []
            
            remaining = line[len(manufacturer):].strip()
            
            # Extract RQ from end
            rq_match = re.search(r'\s+(Yes|No\s*\([^)]+\))\s*$', remaining, re.IGNORECASE)
            
            rq = False
            model_number = ''
            
            if rq_match:
                rq_text = rq_match.group(1).strip()
                remaining = remaining[:rq_match.start()].strip()
                
                if rq_text.lower() == 'yes':
                    rq = True
                else:
                    no_match = re.search(r'No\s*\(([^)]+)\)', rq_text, re.IGNORECASE)
                    if no_match:
                        model_number = no_match.group(1).strip()
            
            # Parse model
            parts = re.split(r'\s{2,}', remaining)
            model_text = parts[0].strip() if parts else remaining
            
            # Split concatenated models
            models = self._split_concatenated_models(model_text, manufacturer)
            
            for model in models:
                if not model or len(model) < 2:
                    continue
                
                device = {
                    "name": f"{manufacturer} {model}",
                    "manufacturer": manufacturer,
                    "model": model,
                    "model_number": model_number,
                    "os_version": self._extract_android_version(model),
                    "rationally_qualified": rq,
                    "product": product,
                    "region": self.region
                }
                
                devices.append(device)
        
        return devices
    
    
    def _extract_ios_version(self, model: str) -> str:
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
    
    
    def _extract_android_version(self, model: str) -> str:
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
    
    
    def _calculate_confidence(self, devices: List[Dict], tables_found: int) -> float:
        """Calculate confidence score for extraction."""
        
        if not devices:
            return 0.0
        
        score = 0.0
        
        # Device count (more is better)
        if len(devices) > 50:
            score += 0.4
        elif len(devices) > 10:
            score += 0.3
        elif len(devices) > 0:
            score += 0.1
        
        # Tables found
        if tables_found >= 6:
            score += 0.3
        elif tables_found >= 3:
            score += 0.2
        
        # Data quality
        valid_names = sum(1 for d in devices if d.get('name') and len(d['name']) > 3)
        if len(devices) > 0 and valid_names / len(devices) > 0.9:
            score += 0.3
        
        return min(1.0, score)


def parse_eversense_pdf(pdf_path: str, region: str = "US") -> Dict[str, Any]:
    """Main parsing function using universal extractor."""
    
    extractor = UniversalPDFExtractor(pdf_path, region)
    result = extractor.extract()
    
    # Organize devices by product and OS
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
    
    # Organize devices with deduplication
    seen_devices = set()
    
    for device in result.devices:
        product = device.get('product', 'E3')
        os_type = device.get('os', 'android')
        
        if product in compatibility_data["products"] and os_type in compatibility_data["products"][product]:
            # Create unique key for deduplication - FIXED: use 'region' not 'self.region'
            device_key = f"{product}|{os_type}|{device['name']}|{region}"
            
            # Check for duplicates
            if device_key not in seen_devices:
                seen_devices.add(device_key)
                compatibility_data["products"][product][os_type].append(device)
    
    return compatibility_data
    }
    
    # Organize devices with deduplication
    seen_devices = set()
    
    for device in result.devices:
        product = device.get('product', 'E3')
        os_type = device.get('os', 'android')
        
        if product in compatibility_data["products"] and os_type in compatibility_data["products"][product]:
            # Create unique key for deduplication
            device_key = f"{product}|{os_type}|{device['name']}|{self.region}"
            
            # Check for duplicates
            if device_key not in seen_devices:
                seen_devices.add(device_key)
                compatibility_data["products"][product][os_type].append(device)
    
    return compatibility_data
