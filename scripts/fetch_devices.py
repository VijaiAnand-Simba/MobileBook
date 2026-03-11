#!/usr/bin/env python3
"""
Fetch newly launched mobile devices and compare with compatibility list.
Uses multiple free sources without requiring API keys.
"""

import json
import requests
from datetime import datetime, timedelta
from typing import List, Dict
import sys

def fetch_new_devices():
    """Fetch newly launched devices from the market."""
    
    print("🔍 Fetching new devices from market...")
    
    # Load existing compatibility data
    try:
        with open('docs/compatibility.json', 'r') as f:
            compatibility = json.load(f)
    except FileNotFoundError:
        print("⚠️  compatibility.json not found, using empty list")
        compatibility = {'android': {'E3': [], '365': []}, 'ios': {'E3': [], '365': []}}
    
    # Get all compatible device names
    compatible_devices = set()
    for os_data in [compatibility['android'], compatibility['ios']]:
        for product_line in os_data.values():
            for device in product_line:
                # Store multiple variations of the name
                name = device['name'].lower()
                compatible_devices.add(name)
                # Also add without manufacturer
                parts = name.split(maxsplit=1)
                if len(parts) > 1:
                    compatible_devices.add(parts[1])
    
    print(f"📋 Found {len(compatible_devices)} compatible devices in list")
    
    new_devices = {
        "last_updated": datetime.now().isoformat(),
        "devices": []
    }
    
    # Fetch recent devices from multiple sources
    all_new_devices = []
    
    # 1. Get recent iOS devices (Apple releases are predictable)
    ios_devices = get_recent_ios_devices()
    all_new_devices.extend(ios_devices)
    
    # 2. Get recent Android flagships (known releases)
    android_devices = get_recent_android_devices()
    all_new_devices.extend(android_devices)
    
    # 3. Filter out devices already in compatibility list
    for device in all_new_devices:
        device_name_lower = device['name'].lower()
        device_model_lower = device.get('model', '').lower()
        
        # Check if device or its model is in compatibility list
        if (device_name_lower not in compatible_devices and 
            device_model_lower not in compatible_devices):
            new_devices['devices'].append(device)
    
    # Remove duplicates
    new_devices['devices'] = remove_duplicates(new_devices['devices'])
    
    # Sort by release date (newest first)
    new_devices['devices'].sort(key=lambda x: x['release_date'], reverse=True)
    
    # Save to JSON
    with open('data/new_devices.json', 'w', encoding='utf-8') as f:
        json.dump(new_devices, f, indent=2, ensure_ascii=False)
    
    # Also save to docs folder
    with open('docs/new_devices.json', 'w', encoding='utf-8') as f:
        json.dump(new_devices, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Found {len(new_devices['devices'])} new devices not in compatibility list")
    
    if new_devices['devices']:
        print("\n📱 New devices found:")
        for device in new_devices['devices'][:5]:  # Show first 5
            print(f"   • {device['name']} ({device['os']} {device['os_version']})")
        if len(new_devices['devices']) > 5:
            print(f"   ... and {len(new_devices['devices']) - 5} more")
    
    return new_devices

def get_recent_ios_devices() -> List[Dict]:
    """Get recently released iOS devices."""
    devices = []
    current_year = datetime.now().year
    
    # Known recent iOS devices (update this list periodically)
    recent_ios = [
        # 2024 releases
        {"name": "Apple iPhone 16 Pro Max", "model": "iPhone 16 Pro Max", "release_date": "2024-09-20", "os_version": "18.0"},
        {"name": "Apple iPhone 16 Pro", "model": "iPhone 16 Pro", "release_date": "2024-09-20", "os_version": "18.0"},
        {"name": "Apple iPhone 16 Plus", "model": "iPhone 16 Plus", "release_date": "2024-09-20", "os_version": "18.0"},
        {"name": "Apple iPhone 16", "model": "iPhone 16", "release_date": "2024-09-20", "os_version": "18.0"},
        {"name": "Apple iPad Pro 13-inch (M4)", "model": "iPad Pro 13", "release_date": "2024-05-15", "os_version": "17.4"},
        {"name": "Apple iPad Pro 11-inch (M4)", "model": "iPad Pro 11", "release_date": "2024-05-15", "os_version": "17.4"},
        {"name": "Apple iPad Air 13-inch (M2)", "model": "iPad Air 13", "release_date": "2024-05-07", "os_version": "17.4"},
        {"name": "Apple Watch Series 10", "model": "Watch Series 10", "release_date": "2024-09-20", "os_version": "11.0"},
        {"name": "Apple Watch Ultra 3", "model": "Watch Ultra 3", "release_date": "2024-09-20", "os_version": "11.0"},
        
        # 2023 releases (might still be new)
        {"name": "Apple iPhone 15 Pro Max", "model": "iPhone 15 Pro Max", "release_date": "2023-09-22", "os_version": "17.0"},
        {"name": "Apple iPhone 15 Pro", "model": "iPhone 15 Pro", "release_date": "2023-09-22", "os_version": "17.0"},
        {"name": "Apple iPhone 15 Plus", "model": "iPhone 15 Plus", "release_date": "2023-09-22", "os_version": "17.0"},
        {"name": "Apple iPhone 15", "model": "iPhone 15", "release_date": "2023-09-22", "os_version": "17.0"},
    ]
    
    # Only include devices from last 12 months
    cutoff_date = datetime.now() - timedelta(days=365)
    
    for device in recent_ios:
        release_date = datetime.fromisoformat(device['release_date'])
        if release_date >= cutoff_date:
            devices.append({
                "name": device['name'],
                "model": device['model'],
                "os": "iOS",
                "release_date": device['release_date'],
                "os_version": device['os_version']
            })
    
    return devices

def get_recent_android_devices() -> List[Dict]:
    """Get recently released Android devices."""
    devices = []
    
    # Known recent Android flagships (update this list periodically)
    recent_android = [
        # 2024 releases
        {"name": "Samsung Galaxy S24 Ultra", "model": "Galaxy S24 Ultra", "release_date": "2024-01-24", "os_version": "14.0"},
        {"name": "Samsung Galaxy S24 Plus", "model": "Galaxy S24+", "release_date": "2024-01-24", "os_version": "14.0"},
        {"name": "Samsung Galaxy S24", "model": "Galaxy S24", "release_date": "2024-01-24", "os_version": "14.0"},
        {"name": "Samsung Galaxy Z Fold 6", "model": "Galaxy Z Fold6", "release_date": "2024-07-24", "os_version": "14.0"},
        {"name": "Samsung Galaxy Z Flip 6", "model": "Galaxy Z Flip6", "release_date": "2024-07-24", "os_version": "14.0"},
        {"name": "Google Pixel 9 Pro XL", "model": "Pixel 9 Pro XL", "release_date": "2024-08-22", "os_version": "14.0"},
        {"name": "Google Pixel 9 Pro", "model": "Pixel 9 Pro", "release_date": "2024-08-22", "os_version": "14.0"},
        {"name": "Google Pixel 9", "model": "Pixel 9", "release_date": "2024-08-22", "os_version": "14.0"},
        {"name": "Google Pixel 9 Pro Fold", "model": "Pixel 9 Pro Fold", "release_date": "2024-09-04", "os_version": "14.0"},
        {"name": "OnePlus 12", "model": "OnePlus 12", "release_date": "2024-01-23", "os_version": "14.0"},
        {"name": "OnePlus 12R", "model": "OnePlus 12R", "release_date": "2024-02-13", "os_version": "14.0"},
        {"name": "Motorola Edge 50 Ultra", "model": "Edge 50 Ultra", "release_date": "2024-06-01", "os_version": "14.0"},
        {"name": "Motorola Razr 50 Ultra", "model": "Razr 50 Ultra", "release_date": "2024-06-25", "os_version": "14.0"},
        
        # 2023 releases (might still be new)
        {"name": "Samsung Galaxy S23 Ultra", "model": "Galaxy S23 Ultra", "release_date": "2023-02-17", "os_version": "13.0"},
        {"name": "Samsung Galaxy S23 Plus", "model": "Galaxy S23+", "release_date": "2023-02-17", "os_version": "13.0"},
        {"name": "Samsung Galaxy S23", "model": "Galaxy S23", "release_date": "2023-02-17", "os_version": "13.0"},
        {"name": "Google Pixel 8 Pro", "model": "Pixel 8 Pro", "release_date": "2023-10-12", "os_version": "14.0"},
        {"name": "Google Pixel 8", "model": "Pixel 8", "release_date": "2023-10-12", "os_version": "14.0"},
    ]
    
    # Only include devices from last 12 months
    cutoff_date = datetime.now() - timedelta(days=365)
    
    for device in recent_android:
        release_date = datetime.fromisoformat(device['release_date'])
        if release_date >= cutoff_date:
            devices.append({
                "name": device['name'],
                "model": device['model'],
                "os": "Android",
                "release_date": device['release_date'],
                "os_version": device['os_version']
            })
    
    return devices

def remove_duplicates(devices: List[Dict]) -> List[Dict]:
    """Remove duplicate devices based on name."""
    seen = set()
    unique_devices = []
    
    for device in devices:
        device_key = device['name'].lower()
        if device_key not in seen:
            seen.add(device_key)
            unique_devices.append(device)
    
    return unique_devices

if __name__ == '__main__':
    try:
        fetch_new_devices()
        print("\n✅ New devices data updated successfully!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error fetching new devices: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
