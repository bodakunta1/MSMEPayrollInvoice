from urllib.parse import urlparse

from django.conf import settings
from playwright.sync_api import sync_playwright


def render_url_to_pdf_bytes(url, request):
    """
    Opens the already-existing HTML page in headless Chromium
    and prints it to PDF.

    This makes the browser page and downloaded PDF use the same layout.
    """

    parsed_url = urlparse(url)
    session_cookie_value = request.COOKIES.get(settings.SESSION_COOKIE_NAME)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        context = browser.new_context()

        if session_cookie_value:
            context.add_cookies(
                [
                    {
                        "name": settings.SESSION_COOKIE_NAME,
                        "value": session_cookie_value,
                        "domain": parsed_url.hostname,
                        "path": "/",
                        "httpOnly": True,
                        "secure": parsed_url.scheme == "https",
                    }
                ]
            )

        page = context.new_page()

        page.goto(url, wait_until="networkidle")
        page.emulate_media(media="print")

        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            margin={
                "top": "0mm",
                "right": "0mm",
                "bottom": "0mm",
                "left": "0mm",
            },
        )

        browser.close()

    return pdf_bytes