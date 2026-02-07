"""
Test accessing jobs.uber.com to find job postings
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
import json

async def test_jobs_uber():
    """Try to access jobs.uber.com"""

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
    }

    urls_to_try = [
        'https://jobs.uber.com/en/',
        'https://jobs.uber.com/en/teams/engineering/',
        'https://jobs.uber.com/api/jobs',
        'https://jobs.uber.com/api/v1/jobs',
    ]

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        for url in urls_to_try:
            print(f"\n=== Testing: {url} ===")
            try:
                response = await client.get(url, headers=headers)
                print(f"Status: {response.status_code}")
                print(f"Content-Type: {response.headers.get('content-type', 'N/A')}")
                print(f"Content length: {len(response.text)}")

                if response.status_code == 200:
                    # Check if it's JSON
                    try:
                        data = response.json()
                        print(f"JSON response! Keys: {list(data.keys()) if isinstance(data, dict) else 'array'}")
                        if isinstance(data, list) and len(data) > 0:
                            print(f"First item: {data[0]}")
                        elif isinstance(data, dict):
                            print(f"Sample: {str(data)[:200]}")
                    except:
                        # It's HTML, analyze it
                        soup = BeautifulSoup(response.text, 'html.parser')

                        # Look for job listings
                        job_links = soup.find_all('a', href=lambda x: x and '/en/jobs/' in x)
                        print(f"Found {len(job_links)} job links")
                        if job_links:
                            for link in job_links[:3]:
                                print(f"  - {link.get('href')}: {link.get_text(strip=True)[:50]}")

                        # Look for script tags with data
                        scripts = soup.find_all('script')
                        for script in scripts:
                            if script.string and 'window.__INITIAL_STATE__' in script.string:
                                print("Found window.__INITIAL_STATE__!")
                                # Try to extract the data
                                start = script.string.find('window.__INITIAL_STATE__')
                                if start != -1:
                                    print(f"Preview: {script.string[start:start+500]}")

            except Exception as e:
                print(f"Error: {e}")

    # Try to find the API endpoint by checking network pattern
    print("\n=== Trying common API patterns ===")
    api_attempts = [
        'https://careersapi.uber.com/jobs',
        'https://api-careers.uber.com/jobs',
        'https://jobs.uber.com/api/search',
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for url in api_attempts:
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    print(f"{url}: SUCCESS! {len(response.text)} bytes")
                else:
                    print(f"{url}: {response.status_code}")
            except Exception as e:
                print(f"{url}: {e}")

if __name__ == "__main__":
    asyncio.run(test_jobs_uber())
