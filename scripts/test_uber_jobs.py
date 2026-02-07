"""
Test script to find working method for Uber job postings
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
import json

async def test_uber_careers():
    """Try different methods to get Uber job postings"""

    # Method 1: Career page with browser headers
    print("\n=== Method 1: Career page with browser headers ===")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        try:
            response = await client.get('https://www.uber.com/us/en/careers/list/', headers=headers)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print(f"Success! Content length: {len(response.text)}")
                # Try to find job data in the HTML
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for script tags with job data
                scripts = soup.find_all('script', type='application/ld+json')
                for script in scripts:
                    try:
                        data = json.loads(script.string)
                        print(f"Found JSON-LD data: {data.get('@type', 'unknown')}")
                    except:
                        pass

                # Look for common job listing patterns
                job_elements = soup.find_all(['div', 'li'], class_=lambda x: x and ('job' in x.lower() or 'position' in x.lower() or 'role' in x.lower()))
                print(f"Found {len(job_elements)} potential job elements")
            else:
                print(f"Failed: {response.status_code}")
                print(f"Headers: {response.headers}")
        except Exception as e:
            print(f"Error: {e}")

    # Method 2: Try Uber API with different endpoints
    print("\n=== Method 2: Try Uber internal API ===")
    api_urls = [
        'https://www.uber.com/api/loadSearchJobsResults',
        'https://careersapi.uber.com/v1/jobs',
        'https://www.uber.com/api/careers/jobs',
    ]

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        for url in api_urls:
            try:
                response = await client.get(url, headers=headers)
                print(f"{url}: {response.status_code}")
                if response.status_code == 200:
                    print(f"Success! Content preview: {response.text[:200]}")
            except Exception as e:
                print(f"{url}: Error - {e}")

    # Method 3: Check if Uber uses Lever ATS
    print("\n=== Method 3: Check Lever ATS ===")
    lever_url = "https://api.lever.co/v0/postings/uber"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(lever_url)
            print(f"Lever API: {response.status_code}")
            if response.status_code == 200:
                jobs = response.json()
                print(f"Found {len(jobs)} jobs via Lever!")
                # Print first job as sample
                if jobs:
                    print(f"Sample job: {jobs[0].get('text', 'N/A')}")
    except Exception as e:
        print(f"Lever API error: {e}")

    # Method 4: Check for LinkedIn job search
    print("\n=== Method 4: LinkedIn Jobs API ===")
    print("Note: LinkedIn requires authentication and has rate limits")
    print("Would need to register for LinkedIn Jobs API access")

if __name__ == "__main__":
    asyncio.run(test_uber_careers())
