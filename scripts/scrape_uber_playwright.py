"""
Use Playwright to scrape Uber jobs page (renders JavaScript)
"""

import asyncio
from playwright.async_api import async_playwright
import json

async def scrape_uber_jobs():
    """Scrape Uber jobs using Playwright"""

    async with async_playwright() as p:
        # Launch browser (headless mode)
        print("Launching browser...")
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Set a realistic user agent
        await page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        print("Navigating to Uber careers page...")
        try:
            # Try the main listing page
            await page.goto('https://www.uber.com/us/en/careers/list/', wait_until='networkidle', timeout=60000)
            print(f"Page loaded: {page.url}")

            # Wait for job listings to load (adjust selector as needed)
            print("Waiting for content to load...")
            await page.wait_for_timeout(5000)  # Wait 5 seconds for JavaScript to render

            # Get the page content
            content = await page.content()
            print(f"Page content length: {len(content)}")

            # Try to find job elements
            # Common selectors for job listings
            selectors_to_try = [
                '[data-test="job-card"]',
                '[data-testid="job-card"]',
                '.job-listing',
                '.job-card',
                '[class*="job"]',
                'a[href*="/en/jobs/"]',
            ]

            jobs_found = []
            for selector in selectors_to_try:
                elements = await page.query_selector_all(selector)
                if elements:
                    print(f"Found {len(elements)} elements with selector: {selector}")
                    for elem in elements[:5]:  # Sample first 5
                        text = await elem.text_content()
                        href = await elem.get_attribute('href')
                        jobs_found.append({'text': text, 'href': href})

            # Also check if jobs.uber.com loads
            print("\n=== Trying jobs.uber.com ===")
            await page.goto('https://jobs.uber.com/en/', wait_until='networkidle', timeout=60000)
            print(f"Status: {page.url}")

            await page.wait_for_timeout(5000)

            # Look for job links
            job_links = await page.query_selector_all('a[href*="/en/jobs/"]')
            print(f"Found {len(job_links)} job links")

            jobs_data = []
            for link in job_links[:10]:  # Sample first 10
                title = await link.text_content()
                href = await link.get_attribute('href')
                jobs_data.append({'title': title.strip(), 'url': href})

            if jobs_data:
                print("\n=== Sample Jobs ===")
                for job in jobs_data[:5]:
                    print(f"  - {job['title'][:60]}: {job['url']}")

                print(f"\nTotal jobs found: {len(job_links)}")

            # Save full page HTML for analysis
            with open('/tmp/uber_jobs_rendered.html', 'w') as f:
                f.write(await page.content())
            print("\n=== Saved rendered HTML to /tmp/uber_jobs_rendered.html ===")

        except Exception as e:
            print(f"Error: {e}")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_uber_jobs())
