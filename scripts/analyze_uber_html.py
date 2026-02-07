"""
Analyze Uber careers page HTML to find where job data is loaded from
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
import json
import re

async def analyze_page():
    """Download and analyze Uber careers page"""

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
    }

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        response = await client.get('https://www.uber.com/us/en/careers/list/', headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Content length: {len(response.text)}")

        if response.status_code != 200:
            print("Failed to fetch page")
            return

        soup = BeautifulSoup(response.text, 'html.parser')

        # Look for all script tags
        print("\n=== Analyzing script tags ===")
        scripts = soup.find_all('script')
        print(f"Found {len(scripts)} script tags")

        for i, script in enumerate(scripts):
            if script.string and len(script.string) > 100:
                # Look for potential API URLs or data
                if 'job' in script.string.lower() or 'career' in script.string.lower() or 'position' in script.string.lower():
                    print(f"\n--- Script {i} (contains job-related content) ---")
                    print(script.string[:500])

        # Look for API endpoints in the HTML
        print("\n=== Looking for API endpoints ===")
        api_patterns = [
            r'https?://[^"\s]+api[^"\s]+job[^"\s]*',
            r'https?://[^"\s]+job[^"\s]+api[^"\s]*',
            r'https?://[^"\s]+career[^"\s]*',
            r'/api/[^"\s]+job[^"\s]*',
        ]

        all_text = response.text
        for pattern in api_patterns:
            matches = re.findall(pattern, all_text, re.IGNORECASE)
            if matches:
                print(f"Pattern '{pattern}' found:")
                unique_matches = list(set(matches))[:5]  # Show up to 5 unique matches
                for match in unique_matches:
                    print(f"  - {match}")

        # Look for JSON data
        print("\n=== Looking for embedded JSON data ===")
        json_pattern = r'window\.__[A-Z_]+__\s*=\s*(\{.+?\});'
        json_matches = re.findall(json_pattern, all_text, re.DOTALL)

        for i, match in enumerate(json_matches[:3]):  # Analyze first 3
            try:
                data = json.loads(match)
                print(f"\nFound window data object {i}:")
                print(f"Keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
                if isinstance(data, dict) and len(str(data)) < 1000:
                    print(f"Data: {data}")
            except:
                print(f"Window object {i} is not valid JSON")

        # Save HTML for manual inspection
        with open('/tmp/uber_careers.html', 'w') as f:
            f.write(response.text)
        print("\n=== HTML saved to /tmp/uber_careers.html for manual inspection ===")

if __name__ == "__main__":
    asyncio.run(analyze_page())
