from urllib.parse import urlparse

from django.conf import settings
from playwright.sync_api import sync_playwright


def _add_session_cookie(context, request, url):
    session_cookie_value = request.COOKIES.get(settings.SESSION_COOKIE_NAME)

    if not session_cookie_value:
        return

    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

    context.add_cookies(
        [
            {
                "name": settings.SESSION_COOKIE_NAME,
                "value": session_cookie_value,
                "url": base_url,
                "httpOnly": True,
                "secure": parsed_url.scheme == "https",
            }
        ]
    )


def render_url_to_pdf_bytes(url, request):
    """
    Render one logged-in Django HTML page to PDF.
    """

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()

        _add_session_cookie(context, request, url)

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


def render_many_urls_to_pdf_bytes(items, request):
    """
    Render multiple logged-in Django HTML pages to PDFs.

    items format:
    [
        ("filename1.pdf", "http://127.0.0.1:8000/payroll/lines/1/form-xix/"),
        ("filename2.pdf", "http://127.0.0.1:8000/payroll/lines/2/form-xix/"),
    ]

    Returns:
    [
        ("filename1.pdf", b"...pdf bytes..."),
        ("filename2.pdf", b"...pdf bytes..."),
    ]
    """

    if not items:
        return []

    first_url = items[0][1]

    rendered_files = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()

        _add_session_cookie(context, request, first_url)

        page = context.new_page()

        for filename, url in items:
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

            rendered_files.append((filename, pdf_bytes))

        browser.close()

    return rendered_files