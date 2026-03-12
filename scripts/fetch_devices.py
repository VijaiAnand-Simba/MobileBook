#!/usr/bin/env python3
"""
Fetch newly launched mobile devices and compare with compatibility list.
Uses public device APIs instead of static lists.
"""

import json
import requests
from datetime import datetime
from typing import List, Dict
import sys


def fetch_new_devices():
    print("🔍 Fetching new devices from market...")

    # Load compatibility list with better error handling
    compatibility = {'android': {'E3': [], '365': []}, 'ios': {'E3': [], '365': []}}
    
    try:
        with open('docs/compatibility.json', 'r') as f:
            loaded = json.load(f)
            # Validate structure
            if isinstance(loaded, dict) and 'android' in loaded and 'ios' in loaded:
                compatibility = loaded
            else:
                print("⚠️ compatibility.json has invalid structure, using defaults")
    except FileNotFoundError:
        print("⚠️ compatibility.json not found, using defaults")
    except json.JSONDecodeError as e:
        print(f"⚠️ compatibility.json is not valid JSON: {e}")
    except Exception as e:
        print(f"⚠️ Error loading compatibility.json: {e}")

    compatible_devices = set()

    # Safely iterate with .get() to handle missing keys
    for os_type in ['android', 'ios']:
        os_data = compatibility.get(os_type, {})
        for product_line in os_data.values():
            if isinstance(product_line, list):
                for device in product_line:
                    if isinstance(device, dict):
                        name = device.get('name', '').lower()
                        if name:
                            compatible_devices.add(name)
                            parts = name.split(maxsplit=1)
                            if len(parts) > 1:
                                compatible_devices.add(parts[1])

    print(f"📋 Loaded {len(compatible_devices)} compatible device names/variants")
    
    # DEBUG: Show sample of compatible devices
    if compatible_devices:
        print(f"   Sample: {list(compatible_devices)[:5]}")

    new_devices = {
        "last_updated": datetime.now().isoformat(),
        "devices": []
    }

    market_devices = fetch_market_devices()
    
    # DEBUG: Show what we got from API
    print(f"🌐 API returned {len(market_devices)} devices")
    if market_devices:
        print(f"   First device: {market_devices[0]}")

    for device in market_devices:
        name = device["name"].lower()
        model = device.get("model", "").lower()

        is_compatible = name in compatible_devices or model in compatible_devices
        
        # DEBUG: Show first few comparisons
        if len(new_devices["devices"]) < 3 and not is_compatible:
            print(f"   ✨ New: {device['name'][:50]} (not in compatibility list)")

        if not is_compatible:
            new_devices["devices"].append(device)

    new_devices["devices"] = remove_duplicates(new_devices["devices"])

    new_devices["devices"].sort(
        key=lambda x: x["release_date"], reverse=True
    )

    save_results(new_devices)

    print(f"\n✅ Found {len(new_devices['devices'])} new devices")

    if new_devices["devices"]:
        print("\n📱 New devices:")
        for d in new_devices["devices"][:10]:
            print(f"   • {d['name']} ({d['os']} {d.get('os_version', 'N/A')})")
    else:
        print("\n💡 No new devices found. All API devices match compatibility list.")

    return new_devices


def fetch_market_devices():
    """Fetch latest devices from GSMArena."""

    devices = []

    try:
        print("🌍 Fetching devices from GSMArena...")

        url = "https://www.gsmarena.com/makers.php3"
        r = requests.get(url, timeout=20)

        if r.status_code != 200:
            print("⚠️ Failed to fetch makers list")
            return devices

        # Simple fallback list of popular brands
        brands = [
            "samsung-phones-9",
            "apple-phones-48",
            "xiaomi-phones-80",
            "oneplus-phones-95",
            "google-phones-107",
            "motorola-phones-4"
        ]

        for brand in brands:

            brand_url = f"https://www.gsmarena.com/{brand}.php"

            try:
                res = requests.get(brand_url, timeout=20)

                if res.status_code != 200:
                    continue

                from bs4 import BeautifulSoup

                soup = BeautifulSoup(res.text, "html.parser")

                phones = soup.select(".makers li")

                for p in phones[:10]:  # only latest models

                    name = p.find("span").text.strip()

                    devices.append({
                        "name": name,
                        "model": name,
                        "os": "Android" if "iPhone" not in name else "iOS",
                        "os_version": "",
                        "release_date": datetime.now().strftime("%Y-%m-%d")
                    })

            except Exception as e:
                print("⚠️ brand fetch failed:", brand, e)

    except Exception as e:
        print("⚠️ Device fetch failed:", e)

    print(f"🌐 Collected {len(devices)} devices")

    return devices


def remove_duplicates(devices: List[Dict]) -> List[Dict]:
    seen = set()
    result = []

    for device in devices:
        key = device["name"].lower()

        if key not in seen:
            seen.add(key)
            result.append(device)

    return result


def save_results(data):
    import os
    
    # Ensure directories exist
    os.makedirs("data", exist_ok=True)
    os.makedirs("docs", exist_ok=True)
    
    with open("data/new_devices.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    with open("docs/new_devices.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    try:
        fetch_new_devices()
        print("\n✅ Device list updated successfully")
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
