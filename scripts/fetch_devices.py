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


DEVICE_API = "https://api-mobilespecs.azharimm.dev/v2/latest"


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


def fetch_market_devices() -> List[Dict]:
    devices = []

    try:
        print("🌍 Fetching devices from public API...")

        r = requests.get(DEVICE_API, timeout=20)
        r.raise_for_status()
        
        data = r.json()
        
        # DEBUG: Show API response structure
        print(f"   API response keys: {data.keys() if isinstance(data, dict) else 'Not a dict'}")

        api_data = data.get("data", [])
        print(f"   Found {len(api_data)} devices in response")

        for item in api_data:
            name = item.get("phone_name", "")
            slug = item.get("slug", "")

            if not name:  # Skip empty names
                continue

            os = "Android"

            if "iphone" in name.lower() or "ipad" in name.lower():
                os = "iOS"

            devices.append({
                "name": name,
                "model": slug,
                "os": os,
                "os_version": "",
                "release_date": datetime.now().strftime("%Y-%m-%d")
            })

    except requests.exceptions.RequestException as e:
        print(f"⚠️ API request failed: {e}")
    except Exception as e:
        print(f"⚠️ API fetch failed: {e}")

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
