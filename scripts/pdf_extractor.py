#!/usr/bin/env python3
"""
Universal PDF extractor with multiple fallback strategies.
Handles text transformations, rotations, format changes, concatenated devices, and malformed NOW tables.
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
        models = re.split(r',\s*(?:and\s+)?|;\s*|\s+and\s+|\s+&\s+', text)
        
        cleaned_models = []
        for model in models:
            model = model.strip()
            model = re.sub(r'^(and|or)\s+', '', model, flags=re.IGNORECASE).strip()
            model = re.sub(r'[,;.]$', '', model).strip()
            
            if len(model) < 2:
                continue
            
            skip_patterns = [
                r'^table\s+\d+',
                r'rationally\s+qualified',
                r'^see\s+',
                r'^note\s*:',
                r'^version\s+',
                r'^\d+\.\d+$',
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
        
        if manufacturer.lower() == 'apple':
            return os_type == 'ios'
        
        if manufacturer in self.KNOWN_MANUFACTURERS:
            return os_type == 'android'
        
        return False
    
    
    def _extract_multiple_iphone_models(self, text: str) -> List[str]:
        """Extract multiple iPhone models from concatenated text."""
        models = []
        pattern = r'iPhone\s+(?:\d+\s*(?:Pro\s*(?:Max)?|Plus|Mini)?|SE(?:\s+\(\d+(?:st|nd|rd|th)\s+generation\))?|X[RS]?(?:\s+Max)?)'
        
        matches = re.finditer(pattern, text, re.IGNORECASE)
        seen = set()
        
        for match in matches:
            model = match.group(0).strip()
            model = ' '.join(model.split())
            
            if model in seen or model.lower() in ['confidential', 'rationally', 'qualified']:
                continue
            
            seen.add(model)
            models.append(model)
        
        if not models:
            models = self._split_concatenated_models(text, '')
        
        return models
    
    
    def _try_pdfplumber_tables(self) -> ExtractionResult:
        """Extract using pdfplumber's table detection."""
        
        print("\n📊 Trying: pdfplumber table extraction...")
        devices = []
        errors = []
        tables_found = 0
        
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    tables = page.extract_tables()
                    
                    if not tables:
                        continue
                    
                    print(f"   📄 Page {page_num}: Found {len(tables)} table(s)")
                    
                    for table_idx, table in enumerate(tables):
                        if not table or len(table) < 2:
                            print(f"      ⏭️  Table {table_idx+1}: Skipped (empty)")
                            continue
                        
                        tables_found += 1
                        
                        print(f"      📋 Table {table_idx+1}: {len(table)} rows x {len(table[0]) if table[0] else 0} cols")
                        
                        if table[0]:
                            header = [str(cell)[:25] if cell else '' for cell in table[0][:4]]
                            print(f"         Header: {header}")
                        
                        if len(table) > 1 and table[1]:
                            sample = [str(cell)[:25] if cell else '' for cell in table[1][:4]]
                            print(f"         Sample: {sample}")
                        
                        # Check if this is a device table (has "Device Manufacturer" in header)
                        is_device_table = False
                        if table[0]:
                            header_text = ' '.join([str(c) for c in table[0] if c]).lower()
                            is_device_table = 'device manufacturer' in header_text or 'manufacturer' in header_text
                        
                        if is_device_table:
                            print(f"         ✓ Device table detected")
                        
                        table_info = self._identify_table(page, table, page_num)
                        
                        if not table_info and is_device_table:
                            # Manual detection based on page content
                            page_text = page.extract_text()
                            
                            if page_text:
                                page_lower = page_text.lower()
                                
                                # Check for table numbers in surrounding text
                                if 'table 7' in page_lower and 'ios' in page_lower:
                                    table_info = {"product": "NOW", "os": "ios"}
                                    print(f"         ✓ Manual: NOW iOS (Table 7)")
                                elif 'table 8' in page_lower and 'android' in page_lower:
                                    table_info = {"product": "NOW", "os": "android"}
                                    print(f"         ✓ Manual: NOW Android (Table 8)")
                                elif 'table 3' in page_lower:
                                    table_info = {"product": "E3", "os": "ios"}
                                    print(f"         ✓ Manual: E3 iOS (Table 3)")
                                elif 'table 4' in page_lower:
                                    table_info = {"product": "E3", "os": "android"}
                                    print(f"         ✓ Manual: E3 Android (Table 4)")
                                elif 'table 5' in page_lower:
                                    table_info = {"product": "365", "os": "ios"}
                                    print(f"         ✓ Manual: 365 iOS (Table 5)")
                                elif 'table 6' in page_lower:
                                    table_info = {"product": "365", "os": "android"}
                                    print(f"         ✓ Manual: 365 Android (Table 6)")
                        
                        if not table_info:
                            print(f"         ⚠️  Could not identify table type")
                            continue
                        
                        print(f"         ✅ Type: {table_info['product']} / {table_info['os']}")
                        
                        parsed = self._parse_table_rows(
                            table, 
                            table_info['os'], 
                            table_info['product']
                        )
                        
                        devices.extend(parsed)
                        print(f"         ✓ Extracted {len(parsed)} devices")
            
            print(f"\n   📊 Total: {len(devices)} devices")
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
            import traceback
            traceback.print_exc()
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
                    text = page.extract_text()
                    
                    if not text:
                        continue
                    
                    lines = text.split('\n')
                    
                    for line in lines:
                        line = line.strip()
                        
                        if not line:
                            continue
                        
                        table_match = self._detect_table_header(line)
                        if table_match:
                            current_table = table_match
                            header_seen = False
                            continue
                        
                        if current_table and not header_seen:
                            if 'Device Manufacturer' in line or 'Manufacturer' in line:
                                header_seen = True
                                continue
                        
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
            import traceback
            traceback.print_exc()
            return ExtractionResult(False, "pdfplumber_layout", [], 0, 0.0, errors)
    
    
    def _try_pymupdf(self) -> ExtractionResult:
        """Extract using PyMuPDF."""
        
        print("\n📑 Trying: PyMuPDF extraction...")
        devices = []
        errors = []
        
        try:
            doc = fitz.open(self.pdf_path)
            current_table = None
            header_seen = False
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                
                if not text:
                    continue
                
                lines = text.split('\n')
                
                for line in lines:
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    table_match = self._detect_table_header(line)
                    if table_match:
                        current_table = table_match
                        header_seen = False
                        print(f"   Found: {current_table['product']} {current_table['os'].upper()} (Page {page_num+1})")
                        continue
                    
                    if current_table and not header_seen:
                        if 'Device Manufacturer' in line or 'Manufacturer' in line:
                            header_seen = True
                            continue
                    
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
            import traceback
            traceback.print_exc()
            return ExtractionResult(False, "pymupdf", [], 0, 0.0, errors)
    
    
def _detect_table_header(self, line: str) -> Optional[Dict[str, str]]:
    """Detect table type from header line."""
    
    patterns = [
        # E3 patterns
        (r'Table\s+3.*?E3.*?iOS.*?MMA', {"product": "E3", "os": "ios"}),
        (r'Table\s+4.*?E3.*?Android.*?MMA', {"product": "E3", "os": "android"}),
        (r'E3.*?iOS.*?(?:MMA|Compatible)', {"product": "E3", "os": "ios"}),
        (r'E3.*?Android.*?(?:MMA|Compatible)', {"product": "E3", "os": "android"}),
        
        # 365 patterns
        (r'Table\s+5.*?365.*?iOS.*?MMA', {"product": "365", "os": "ios"}),
        (r'Table\s+6.*?365.*?Android.*?MMA', {"product": "365", "os": "android"}),
        (r'365.*?iOS.*?(?:MMA|Compatible)', {"product": "365", "os": "ios"}),
        (r'365.*?Android.*?(?:MMA|Compatible)', {"product": "365", "os": "android"}),
        
        # NOW patterns - EXACT MATCH
        (r'Table\s+7.*?iOS.*?NOW.*?Application', {"product": "NOW", "os": "ios"}),
        (r'Table\s+8.*?Android.*?NOW.*?Application', {"product": "NOW", "os": "android"}),
        (r'NOW.*?iOS.*?(?:App|Application|Compatible)', {"product": "NOW", "os": "ios"}),
        (r'NOW.*?Android.*?(?:App|Application|Compatible)', {"product": "NOW", "os": "android"}),
        (r'iOS.*?NOW.*?Application', {"product": "NOW", "os": "ios"}),
        (r'Android.*?NOW.*?Application', {"product": "NOW", "os": "android"}),
    ]
    
    for pattern, info in patterns:
        if re.search(pattern, line, re.IGNORECASE):
            return info
    
    return None
    
    
def _identify_table(self, page, table: List[List], page_num: int) -> Optional[Dict[str, str]]:
    """Identify table type from nearby text or content."""
    
    # Get full page text
    text = page.extract_text()
    
    if text:
        lines = text.split('\n')
        
        # Look for table numbers first
        table_markers = {
            3: {"product": "E3", "os": "ios"},
            4: {"product": "E3", "os": "android"},
            5: {"product": "365", "os": "ios"},
            6: {"product": "365", "os": "android"},
            7: {"product": "NOW", "os": "ios"},
            8: {"product": "NOW", "os": "android"},
        }
        
        # Check for "Table X" markers
        for table_num, info in table_markers.items():
            pattern = rf'Table\s+{table_num}\s+[–-]'
            if re.search(pattern, text, re.IGNORECASE):
                product = info['product']
                os_type = info['os']
                print(f"         ℹ️  Found Table {table_num}: {product} {os_type.upper()}")
                return info
        
        # Fallback: pattern matching on lines
        for i, line in enumerate(lines):
            if i > 50:
                break
            
            match = self._detect_table_header(line)
            if match:
                return match
        
        # Check for NOW specifically
        for line in lines[:50]:
            line_lower = line.lower()
            
            # NOW iOS (Table 7)
            if 'table 7' in line_lower or ('ios' in line_lower and 'now application' in line_lower):
                print(f"         ℹ️  Found NOW iOS marker: {line[:60]}")
                return {"product": "NOW", "os": "ios"}
            
            # NOW Android (Table 8)
            if 'table 8' in line_lower or ('android' in line_lower and 'now application' in line_lower):
                print(f"         ℹ️  Found NOW Android marker: {line[:60]}")
                return {"product": "NOW", "os": "android"}
    
    # Check table headers
    if table and table[0]:
        first_row = ' '.join(str(cell) for cell in table[0] if cell)
        first_row_lower = first_row.lower()
        
        # Match exact header patterns
        if 'device manufacturer' in first_row_lower or 'manufacturer' in first_row_lower:
            # This is a device table, determine which one from page context
            
            if text:
                text_lower = text.lower()
                
                # Check for table numbers
                if 'table 7' in text_lower or ('ios' in text_lower and 'now' in text_lower):
                    return {"product": "NOW", "os": "ios"}
                elif 'table 8' in text_lower or ('android' in text_lower and 'now' in text_lower):
                    return {"product": "NOW", "os": "android"}
                elif 'table 3' in text_lower or ('e3' in text_lower and 'ios' in text_lower):
                    return {"product": "E3", "os": "ios"}
                elif 'table 4' in text_lower or ('e3' in text_lower and 'android' in text_lower):
                    return {"product": "E3", "os": "android"}
                elif 'table 5' in text_lower or ('365' in text_lower and 'ios' in text_lower):
                    return {"product": "365", "os": "ios"}
                elif 'table 6' in text_lower or ('365' in text_lower and 'android' in text_lower):
                    return {"product": "365", "os": "android"}
        
        # Try pattern matching on first row
        match = self._detect_table_header(first_row)
        if match:
            return match
    
    return None
    
    
    def _parse_table_rows(self, table: List[List], os_type: str, product: str) -> List[Dict]:
        """Parse table rows into device objects."""
        
        if product == 'NOW':
            return self._parse_now_table_rows(table, os_type, product)
        
        devices = []
        
        for i, row in enumerate(table):
            if i == 0:
                continue
            
            if not row or all(cell is None or str(cell).strip() == '' for cell in row):
                continue
            
            row_devices = self._row_to_devices(row, os_type, product)
            if row_devices:
                devices.extend(row_devices)
        
        return devices
    
    
    def _parse_now_table_rows(self, table: List[List], os_type: str, product: str) -> List[Dict]:
        """Special parser for NOW tables."""
        
        devices = []
        
        print(f"      🔧 NOW parser: {os_type} ({len(table)} rows)")
        
        for i, row in enumerate(table):
            if i == 0:
                print(f"         Header: {[str(c)[:20] for c in row[:4]]}")
                continue
            
            if not row:
                continue
            
            row = [str(cell).strip() if cell is not None else '' for cell in row]
            row = [cell for cell in row if cell]
            
            if len(row) < 2:
                continue
            
            if i <= 5:
                print(f"         Row {i}: {[c[:20] for c in row[:4]]}")
            
            manufacturer_cell = row[0]
            model_cell = row[1] if len(row) > 1 else ''
            
            if os_type == 'ios':
                if 'apple' not in manufacturer_cell.lower():
                    continue
                
                apple_count = manufacturer_cell.count('Apple')
                
                if apple_count == 1 and manufacturer_cell.strip() == 'Apple':
                    models = self._extract_multiple_iphone_models(model_cell)
                    
                    if not models:
                        models = [model_cell]
                    
                    for model in models:
                        if model.lower() in ['confidential', 'rationally qualified', 'rationally', 'qualified', '']:
                            continue
                        
                        model = re.sub(r'\s*\(\d+\s*mm\)', '', model).strip()
                        
                        if len(model) < 3:
                            continue
                        
                        rq = False
                        model_number = ''
                        
                        if len(row) > 2:
                            third_col = row[2]
                            if 'rationally' in third_col.lower() or 'qualified' in third_col.lower():
                                rq = True
                            else:
                                model_number = third_col if third_col not in ['', 'Confidential'] else ''
                        
                        device = {
                            "name": f"Apple {model}",
                            "manufacturer": "Apple",
                            "model": model,
                            "model_number": model_number,
                            "os_version": self._extract_ios_version(model),
                            "rationally_qualified": rq,
                            "product": product,
                            "region": self.region
                        }
                        
                        devices.append(device)
                        if i <= 5:
                            print(f"            ✓ {device['name']}")
                
                elif apple_count > 1:
                    models = self._extract_multiple_iphone_models(model_cell)
                    
                    for model in models:
                        if model.lower() in ['confidential', 'rationally', 'qualified', '']:
                            continue
                        
                        model = re.sub(r'\s*\(\d+\s*mm\)', '', model).strip()
                        
                        if len(model) < 3:
                            continue
                        
                        device = {
                            "name": f"Apple {model}",
                            "manufacturer": "Apple",
                            "model": model,
                            "model_number": "",
                            "os_version": self._extract_ios_version(model),
                            "rationally_qualified": True,
                            "product": product,
                            "region": self.region
                        }
                        
                        devices.append(device)
                        if i <= 5:
                            print(f"            ✓ {device['name']}")
            
            else:
                # Android NOW
                if not self._is_valid_manufacturer(manufacturer_cell, 'android'):
                    if i <= 5:
                        print(f"            ✗ Invalid: {manufacturer_cell}")
                    continue
                
                model = model_cell
                
                if not model or len(model) < 2:
                    continue
                
                rq = False
                model_number = ''
                
                if len(row) > 2:
                    third_col = row[2]
                    
                    if third_col.lower() == 'yes':
                        rq = True
                    elif 'no (' in third_col.lower():
                        match = re.search(r'No\s*\(([^)]+)\)', third_col, re.IGNORECASE)
                        if match:
                            model_number = match.group(1)
                    else:
                        model_number = third_col
                    
                    if not rq and len(row) > 3:
                        fourth_col = row[3]
                        if fourth_col.lower() == 'yes':
                            rq = True
                
                device = {
                    "name": f"{manufacturer_cell} {model}",
                    "manufacturer": manufacturer_cell,
                    "model": model,
                    "model_number": model_number,
                    "os_version": self._extract_android_version(model),
                    "rationally_qualified": rq,
                    "product": product,
                    "region": self.region
                }
                
                devices.append(device)
                if i <= 5:
                    print(f"            ✓ {device['name']} (RQ={rq})")
        
        print(f"      ✅ Extracted {len(devices)} NOW devices")
        return devices
    
    
    def _row_to_devices(self, row: List, os_type: str, product: str) -> List[Dict]:
        """Convert table row to device object(s)."""
        
        row = [str(cell).strip() if cell is not None else '' for cell in row]
        row = [cell for cell in row if cell]
        
        if len(row) < 2:
            return []
        
        manufacturer = row[0].strip()
        model_text = row[1].strip() if len(row) > 1 else ''
        
        if not model_text:
            return []
        
        if not self._is_valid_manufacturer(manufacturer, os_type):
            return []
        
        devices = []
        
        if os_type == 'ios':
            model_number = row[2] if len(row) > 2 else ''
            models = self._split_concatenated_models(model_text, manufacturer)
            
            for model in models:
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
                    model_number = row[-2] if row[-2] not in ['Yes', 'No'] else ''
                else:
                    model_number = last_col
            
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
        """Parse a single device line (text-based)."""
        
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
            
            if product == 'NOW':
                models = self._extract_multiple_iphone_models(model_text)
            else:
                models = self._split_concatenated_models(model_text, 'Apple')
            
            for model in models:
                model = re.sub(r'\s*\(\d+\s*mm\)', '', model).strip()
                
                if not model or len(model) < 2:
                    continue
                
                if model.lower() in ['confidential', 'rationally', 'qualified']:
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
            manufacturer = None
            for mfr in self.KNOWN_MANUFACTURERS:
                if line.startswith(mfr):
                    manufacturer = mfr
                    break
            
            if not manufacturer:
                return []
            
            remaining = line[len(manufacturer):].strip()
            
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
            
            parts = re.split(r'\s{2,}', remaining)
            model_text = parts[0].strip() if parts else remaining
            
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
        elif 'iphone 11' in model_lower:
            return '13.0'
        elif 'iphone x' in model_lower:
            return '12.0'
        elif 'iphone 8' in model_lower:
            return '11.0'
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
        
        if len(devices) > 50:
            score += 0.4
        elif len(devices) > 10:
            score += 0.3
        elif len(devices) > 0:
            score += 0.1
        
        if tables_found >= 6:
            score += 0.3
        elif tables_found >= 3:
            score += 0.2
        
        valid_names = sum(1 for d in devices if d.get('name') and len(d['name']) > 3)
        if len(devices) > 0 and valid_names / len(devices) > 0.9:
            score += 0.3
        
        return min(1.0, score)


def parse_eversense_pdf(pdf_path: str, region: str = "US") -> Dict[str, Any]:
    """Main parsing function using universal extractor."""
    
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
    
    for device in result.devices:
        product = device.get('product', 'E3')
        os_type = device.get('os', 'android')
        
        if product in compatibility_data["products"] and os_type in compatibility_data["products"][product]:
            existing_names = [d['name'] for d in compatibility_data["products"][product][os_type]]
            if device['name'] not in existing_names:
                compatibility_data["products"][product][os_type].append(device)
    
    return compatibility_data
