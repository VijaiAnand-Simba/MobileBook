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


name: Fetch New Market Devices

on:
  schedule:
    - cron: '0 12 * * 1'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  fetch-devices:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install requests

      - name: Run device fetch script
        run: |
          python scripts/fetch_devices.py

      - name: Commit updates
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "github-actions"

          git add data/new_devices.json docs/new_devices.json

          if ! git diff --staged --quiet; then
            git commit -m "Update new devices data [automated]"
            git push
          fi
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
