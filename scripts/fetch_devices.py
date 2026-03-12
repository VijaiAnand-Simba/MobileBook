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

    # Load compatibility list
    try:
        with open('docs/compatibility.json', 'r') as f:
            compatibility = json.load(f)
    except FileNotFoundError:
        print("⚠️ compatibility.json not found")
        compatibility = {'android': {'E3': [], '365': []}, 'ios': {'E3': [], '365': []}}

    compatible_devices = set()

    for os_data in [compatibility['android'], compatibility['ios']]:
        for product_line in os_data.values():
            for device in product_line:
                name = device['name'].lower()
                compatible_devices.add(name)

                parts = name.split(maxsplit=1)
                if len(parts) > 1:
                    compatible_devices.add(parts[1])

    print(f"📋 Found {len(compatible_devices)} compatible devices")

    new_devices = {
        "last_updated": datetime.now().isoformat(),
        "devices": []
    }

    market_devices = fetch_market_devices()

    for device in market_devices:

        name = device["name"].lower()
        model = device.get("model", "").lower()

        if name not in compatible_devices and model not in compatible_devices:
            new_devices["devices"].append(device)

    new_devices["devices"] = remove_duplicates(new_devices["devices"])

    new_devices["devices"].sort(
        key=lambda x: x["release_date"], reverse=True
    )

    save_results(new_devices)

    print(f"\n✅ Found {len(new_devices['devices'])} new devices")

    if new_devices["devices"]:
        print("\n📱 New devices:")
        for d in new_devices["devices"][:5]:
            print(f" • {d['name']} ({d['os']} {d['os_version']})")

    return new_devices


def fetch_market_devices() -> List[Dict]:

    devices = []

    try:
        print("🌍 Fetching devices from public API...")

        r = requests.get(DEVICE_API, timeout=20)
        data = r.json()

        for item in data.get("data", []):

            name = item.get("phone_name", "")
            slug = item.get("slug", "")

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

    except Exception as e:
        print("⚠️ API fetch failed:", e)

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

        print("\n❌ Error:", e)
        sys.exit(1)
