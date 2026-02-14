import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth


async def run_test():

    launch_kwargs = {
        "args": ["--headless=new"],
    }

    async with Stealth().use_async(async_playwright()) as p:
        # We launch headless=True because you're in a shell
        browser = await p.chromium.launch(**launch_kwargs)

        # Create a new browser context (like a private window)
        context = await browser.new_context()
        page = await context.new_page()

        # Apply stealth to this page

        print("🌐 Navigating to DuckDuckGo (simple test)...")
        await page.goto("https://duckduckgo.com")

        title = await page.title()
        print(f"✅ Success! Page title is: {title}")

        # Check a bot-detection test site
        print("🕵️ Checking browser fingerprints...")
        await page.goto("https://bot.sannysoft.com/")

        # Take a screenshot to prove it worked (Nix handles the rendering)
        await page.screenshot(path="stealth_test_2.png")
        print("📸 Screenshot saved as 'stealth_test.png'")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(run_test())
