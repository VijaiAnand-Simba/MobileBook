#!/usr/bin/env python3
"""
Fetch newly launched mobile devices and compare with compatibility list.
"""

import json
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Set
import sys
import time
import re


BRANDS = [
    ("samsung",  "https://www.gsmarena.com/samsung-phones-9.php"),
    ("apple",    "https://www.gsmarena.com/apple-phones-48.php"),
    ("xiaomi",   "https://www.gsmarena.com/xiaomi-phones-80.php"),
    ("oneplus",  "https://www.gsmarena.com/oneplus-phones-95.php"),
    ("google",   "https://www.gsmarena.com/google-phones-107.php"),
    ("motorola", "https://www.gsmarena.com/motorola-phones-4.php"),
    ("sony",     "https://www.gsmarena.com/sony-phones-7.php"),
    ("oppo",     "https://www.gsmarena.com/oppo-phones-82.php"),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def load_compatibility() -> Set[str]:
    """
    Load compatible device names from compatibility.json.

    Handles structure:
    {
      "products": {
        "E3": {
          "android": [{"name": "...", "model": "...", ...}],
          "ios":     [{"name": "...", "model": "...", ...}]
        },
        "365": { ... }
      }
    }
    """

    compatible = set()

    try:
        with open("docs/compatibility.json", "r") as f:
            data = json.load(f)

        entries = []

        # ── Structure: {"products": {"E3": {"android": [...], "ios": [...]}, ...}}
        if "products" in data and isinstance(data["products"], dict):
            for product_name, product_data in data["products"].items():
                if not isinstance(product_data, dict):
                    continue
                for os_key in ["android", "ios"]:
                    device_list = product_data.get(os_key, [])
                    if isinstance(device_list, list):
                        entries.extend(device_list)
                        print(f"   📦 {product_name}/{os_key}: {len(device_list)} devices")

        # ── Structure: {"android": {...}, "ios": {...}}  (flat)
        elif "android" in data or "ios" in data:
            for os_key in ["android", "ios"]:
                os_block = data.get(os_key, {})
                if isinstance(os_block, dict):
                    for product_list in os_block.values():
                        if isinstance(product_list, list):
                            entries.extend(product_list)
                elif isinstance(os_block, list):
                    entries.extend(os_block)

        # ── Structure: {"devices": [...]}
        elif "devices" in data and isinstance(data["devices"], list):
            entries.extend(data["devices"])

        # ── Structure: plain list
        elif isinstance(data, list):
            entries = data

        else:
            print("⚠️ Unrecognised compatibility.json structure")

        # ── Extract names and model numbers
        for entry in entries:
            if isinstance(entry, dict):
                # Full name  e.g. "Google Pixel 7"
                name = entry.get("name", "").strip().lower()
                # Model      e.g. "Pixel 7"
                model = entry.get("model", "").strip().lower()
                # Model number e.g. "GVU6C"
                model_number = entry.get("model_number", "").strip().lower()

                for value in [name, model, model_number]:
                    if value:
                        compatible.add(value)
                        # Partial match: "pixel 7" from "google pixel 7"
                        parts = value.split(maxsplit=1)
                        if len(parts) > 1:
                            compatible.add(parts[1])

            elif isinstance(entry, str):
                name = entry.strip().lower()
                if name:
                    compatible.add(name)

        print(f"\n📋 Loaded {len(compatible)} compatible device identifiers")

        if compatible:
            sample = sorted(list(compatible))[:8]
            print(f"   Sample: {sample}")

    except FileNotFoundError:
        print("⚠️ compatibility.json not found — all market devices treated as new")
    except json.JSONDecodeError as e:
        print(f"⚠️ compatibility.json is invalid JSON: {e}")
    except Exception as e:
        print(f"⚠️ Unexpected error reading compatibility.json: {e}")
        import traceback
        traceback.print_exc()

    return compatible


def parse_date_from_text(text: str) -> str:
    """
    Parse date from text like 'Released 2024, March' or 'Exp. release 2025, Q1'.
    Returns YYYY-MM-DD format or empty string.
    """
    if not text:
        return ""
    
    # Pattern: "2024, March" or "2024, Q1" or "March 2024"
    # Try format: "2024, March" or "2024 March"
    match = re.search(r'(\d{4})[,\s]+(\w+)', text)
    if match:
        year = match.group(1)
        month_str = match.group(2).lower()
        
        month_map = {
            'january': '01', 'february': '02', 'march': '03', 'april': '04',
            'may': '05', 'june': '06', 'july': '07', 'august': '08',
            'september': '09', 'october': '10', 'november': '11', 'december': '12',
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
            'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09', 
            'oct': '10', 'nov': '11', 'dec': '12',
            'q1': '03', 'q2': '06', 'q3': '09', 'q4': '12'
        }
        
        month = month_map.get(month_str, '01')
        return f"{year}-{month}-01"
    
    # Try format: "March 2024" or "March, 2024"
    match = re.search(r'(\w+)[,\s]+(\d{4})', text)
    if match:
        month_str = match.group(1).lower()
        year = match.group(2)
        
        month_map = {
            'january': '01', 'february': '02', 'march': '03', 'april': '04',
            'may': '05', 'june': '06', 'july': '07', 'august': '08',
            'september': '09', 'october': '10', 'november': '11', 'december': '12',
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
            'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09', 
            'oct': '10', 'nov': '11', 'dec': '12',
            'q1': '03', 'q2': '06', 'q3': '09', 'q4': '12'
        }
        
        month = month_map.get(month_str, '01')
        return f"{year}-{month}-01"
    
    # Just year
    match = re.search(r'(\d{4})', text)
    if match:
        return f"{match.group(1)}-01-01"
    
    return ""


def fetch_device_release_date(device_url: str) -> str:
    """Fetch actual release date from device detail page."""
    try:
        r = requests.get(device_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        
        soup = BeautifulSoup(r.text, "lxml")
        
        # Method 1: Check quick specs (top section)
        for span in soup.select(".quickspec-brief span"):
            text = span.get_text(strip=True)
            if "release" in text.lower() or any(month in text.lower() for month in 
                ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                date = parse_date_from_text(text)
                if date:
                    return date
        
        # Method 2: Check specs table - most reliable
        for row in soup.select("table tr, #specs-list tr"):
            header = row.find("td", class_="ttl")
            if header:
                header_text = header.get_text(strip=True).lower()
                if "status" in header_text or "released" in header_text:
                    value_td = row.find("td", class_="nfo")
                    if value_td:
                        date_text = value_td.get_text(strip=True)
                        date = parse_date_from_text(date_text)
                        if date:
                            return date
        
        # Method 3: Check any element with data-spec="released"
        release_elem = soup.find(attrs={"data-spec": "released"})
        if release_elem:
            date_text = release_elem.get_text(strip=True)
            date = parse_date_from_text(date_text)
            if date:
                return date
                
    except Exception as e:
        pass  # Silent fail, will use fallback
    
    return ""


def fetch_brand_devices(brand_name: str, url: str, fetch_dates: bool = True) -> List[Dict]:
    """Fetch latest devices for a single brand from GSMArena."""

    devices = []

    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "lxml")
        items = soup.select(".makers li")

        if not items:
            print(f"   ⚠️ No items found for {brand_name} (selector may have changed)")
            return devices

        for item in items[:15]:
            span = item.find("span")
            link = item.find("a")
            
            if not span:
                continue

            name = span.get_text(strip=True)
            if not name:
                continue

            # Normalize brand name for display
            brand_display = brand_name.capitalize()
            
            # Check if brand name is already in the device name
            brand_variations = [brand_display.lower(), brand_name.lower()]
            has_brand = any(variation in name.lower() for variation in brand_variations)
            
            # Prepend brand name if not already present
            if not has_brand:
                full_name = f"{brand_display} {name}"
            else:
                full_name = name

            os_type = "iOS" if ("iPhone" in name or "iPad" in name or "Watch" in name) else "Android"

            # Extract release date
            release_date = ""
            
            if fetch_dates and link and link.get("href"):
                device_url = f"https://www.gsmarena.com/{link.get('href')}"
                release_date = fetch_device_release_date(device_url)
                
                if release_date:
                    print(f"      📅 {name}: {release_date}")
                else:
                    print(f"      ⚠️ {name}: date not found, using current date")
                
                # Small delay to avoid overwhelming the server
                time.sleep(0.5)
            
            # Fallback to current date if not found
            if not release_date:
                release_date = datetime.now().strftime("%Y-%m-%d")

            devices.append({
                "name":         full_name,
                "brand":        brand_name,
                "model":        name,
                "os":           os_type,
                "os_version":   "",
                "release_date": release_date,
                "source":       "gsmarena"
            })

        print(f"   ✅ {brand_name}: {len(devices)} devices fetched")

    except requests.exceptions.HTTPError as e:
        print(f"   ⚠️ HTTP error for {brand_name}: {e}")
    except requests.exceptions.RequestException as e:
        print(f"   ⚠️ Network error for {brand_name}: {e}")
    except Exception as e:
        print(f"   ⚠️ Parse error for {brand_name}: {e}")

    return devices


def fetch_market_devices(fetch_dates: bool = True) -> List[Dict]:
    """Fetch devices from all configured brands."""

    print("\n🌍 Fetching devices from GSMArena...")
    if fetch_dates:
        print("   📅 Fetching actual release dates (this will take longer)...\n")
    else:
        print("   ⚡ Using current date for all devices (faster mode)\n")
    
    all_devices = []

    for brand_name, url in BRANDS:
        devices = fetch_brand_devices(brand_name, url, fetch_dates=fetch_dates)
        all_devices.extend(devices)

    print(f"\n🌐 Collected {len(all_devices)} devices total")
    return all_devices


def is_new_device(device: Dict, compatible: Set[str]) -> bool:
    """
    Return True if this market device is NOT in the compatibility list.
    Checks name, model slug, and partial name.
    """

    checks = [
        device.get("name",  "").strip().lower(),
        device.get("model", "").strip().lower(),
    ]

    # Also check partial name  e.g. "galaxy s25" from "samsung galaxy s25"
    full_name = device.get("name", "").strip().lower()
    parts = full_name.split(maxsplit=1)
    if len(parts) > 1:
        checks.append(parts[1])

    return not any(c in compatible for c in checks if c)


def remove_duplicates(devices: List[Dict]) -> List[Dict]:
    seen   = set()
    result = []

    for device in devices:
        key = device["name"].lower()
        if key not in seen:
            seen.add(key)
            result.append(device)

    return result


def save_results(data: Dict):
    os.makedirs("data", exist_ok=True)
    os.makedirs("docs", exist_ok=True)

    for path in ["data/new_devices.json", "docs/new_devices.json"]:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    print("💾 Saved → data/new_devices.json & docs/new_devices.json")


def fetch_new_devices(fetch_dates: bool = True):
    print("🔍 Starting device fetch...\n")

    compatible    = load_compatibility()
    market_devices = fetch_market_devices(fetch_dates=fetch_dates)

    new_list = [d for d in market_devices if is_new_device(d, compatible)]
    new_list  = remove_duplicates(new_list)
    new_list.sort(key=lambda x: x["release_date"], reverse=True)

    result = {
        "last_updated": datetime.now().isoformat(),
        "total":        len(new_list),
        "devices":      new_list
    }

    save_results(result)

    print(f"\n✅ {len(new_list)} new (unrecognised) devices found")

    if new_list:
        print("\n📱 New devices (first 10):")
        for d in new_list[:10]:
            print(f"   • {d['name']} [{d['brand']}] ({d['os']}) - Released: {d['release_date']}")
    else:
        print("💡 All market devices already exist in the compatibility list.")

    return result


if __name__ == "__main__":
    try:
        # Check if --no-dates flag is passed for faster execution
        fetch_dates = "--no-dates" not in sys.argv
        
        fetch_new_devices(fetch_dates=fetch_dates)
        print("\n✅ Done")
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
