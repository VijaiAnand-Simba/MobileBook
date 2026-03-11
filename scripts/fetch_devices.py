import requests
import json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

def fetch_new_devices():
    """Fetch newly launched devices from the market."""
    
    # Load existing compatibility data
    with open('data/compatibility.json', 'r') as f:
        compatibility = json.load(f)
    
    # Get all compatible device names
    compatible_devices = set()
    for os_data in [compatibility['android'], compatibility['ios']]:
        for product_line in os_data.values():
            for device in product_line:
                compatible_devices.add(device['name'].lower())
    
    new_devices = {
        "last_updated": datetime.now().isoformat(),
        "devices": []
    }
    
    # Fetch from GSMArena (example - adjust based on actual API/scraping)
    try:
        # Android devices (using example scraping - replace with actual API)
        android_devices = scrape_recent_android_devices()
        
        # iOS devices
        ios_devices = fetch_recent_ios_devices()
        
        all_new_devices = android_devices + ios_devices
        
        # Filter out devices already in compatibility list
        for device in all_new_devices:
            if device['name'].lower() not in compatible_devices:
                new_devices['devices'].append(device)
        
        # Save to JSON
        with open('data/new_devices.json', 'w') as f:
            json.dump(new_devices, f, indent=2)
        
        print(f"✅ Found {len(new_devices['devices'])} new devices not in compatibility list")
        
    except Exception as e:
        print(f"❌ Error fetching devices: {e}")
    
    return new_devices

def scrape_recent_android_devices():
    """Scrape recent Android device launches."""
    devices = []
    cutoff_date = datetime.now() - timedelta(days=90)  # Last 3 months
    
    try:
        # Example scraping (replace with actual implementation)
        url = "https://www.gsmarena.com/news.php3"
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Parse device announcements (adjust selectors based on actual HTML)
        # This is a placeholder implementation
        
        # Alternative: Use actual API if available
        # response = requests.get('https://api.example.com/devices/recent')
        # devices = response.json()
        
    except Exception as e:
        print(f"Warning: Could not fetch Android devices: {e}")
    
    return devices

def fetch_recent_ios_devices():
    """Fetch recent iOS device launches."""
    devices = []
    
    # iOS device list is more controlled - typically from Apple
    known_recent_ios = [
        {"name": "iPhone 15 Pro Max", "os": "iOS", "release_date": "2023-09-22", "os_version": "17.0"},
        {"name": "iPhone 15 Pro", "os": "iOS", "release_date": "2023-09-22", "os_version": "17.0"},
        {"name": "iPhone 15 Plus", "os": "iOS", "release_date": "2023-09-22", "os_version": "17.0"},
        {"name": "iPhone 15", "os": "iOS", "release_date": "2023-09-22", "os_version": "17.0"},
    ]
    
    devices.extend(known_recent_ios)
    
    return devices

if __name__ == '__main__':
    fetch_new_devices()
