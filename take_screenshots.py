"""Take screenshots of all AzerothPanel pages."""
import asyncio
import os
from playwright.async_api import async_playwright

BASE_URL = "http://10.10.20.132"
OUT_DIR = "/root/azerothpanel/docs/screenshots"
os.makedirs(OUT_DIR, exist_ok=True)

PAGES = [
    ("login",           "/login",           None),
    ("dashboard",       "/",                "admin"),
    ("server_control",  "/server",          "admin"),
    ("log_viewer",      "/logs",            "admin"),
    ("players",         "/players",         "admin"),
    ("database",        "/database",        "admin"),
    ("compilation",     "/compilation",     "admin"),
    ("installation",    "/installation",    "admin"),
    ("data_extraction", "/data-extraction", "admin"),
    ("modules",         "/modules",         "admin"),
    ("config_editor",   "/configs",         "admin"),
    ("settings",        "/settings",        "admin"),
]


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # ── Login once ──────────────────────────────────────────────────────
        await page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        await page.screenshot(path=f"{OUT_DIR}/login.png", full_page=True)
        print("  ✓ login")

        await page.get_by_role("textbox", name="admin").fill("admin")
        await page.locator('input[type="password"]').fill("admin")
        await page.get_by_role("button", name="Sign In").click()
        await page.wait_for_url(f"{BASE_URL}/", wait_until="networkidle")

        # ── Remaining pages ──────────────────────────────────────────────────
        for name, path, _ in PAGES[1:]:
            await page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
            # small delay for any JS-driven content to settle
            await page.wait_for_timeout(800)
            out = f"{OUT_DIR}/{name}.png"
            await page.screenshot(path=out, full_page=True)
            print(f"  ✓ {name}")

        await browser.close()
        print("\nAll screenshots saved to docs/screenshots/")


asyncio.run(main())
