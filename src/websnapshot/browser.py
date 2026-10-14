"""Playwright browser renderer for public same-host pages."""
from urllib.parse import urlsplit
from .core import check_public, extract, normalize_url

class BrowserRenderer:
    def __init__(self, start: str, settings: dict):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright fehlt. Bitte pip install -e . und python -m playwright install chromium ausführen.") from exc
        self.host=urlsplit(start).netloc
        self.settings=settings
        self.playwright=sync_playwright().start()
        try:
            self.browser=self.playwright.chromium.launch(headless=True)
            self.context=self.browser.new_context(accept_downloads=False, service_workers="block")
            def guard(route):
                u=route.request.url
                if urlsplit(u).scheme not in ("https","http") or urlsplit(u).netloc != self.host:
                    route.abort()
                    return
                try:
                    check_public(u)
                except ValueError:
                    route.abort()
                    return
                route.continue_()
            self.context.route("**/*",guard)
        except Exception:
            self.playwright.stop()
            raise

    def fetch(self,url: str):
        url=normalize_url(url)
        check_public(url)
        if urlsplit(url).netloc != self.host:
            raise ValueError("Fremde Hosts werden nicht geladen")
        page=self.context.new_page()
        try:
            response=page.goto(url,wait_until="domcontentloaded",timeout=25000)
            if not response or response.status >= 400:
                raise ValueError(f"Browser-Antwort {response.status if response else 'unbekannt'}")
            if urlsplit(page.url).netloc != self.host:
                raise ValueError("Unerlaubte Weiterleitung")
            selector=self.settings.get("wait_selector","")
            if selector:
                page.locator(selector).first.wait_for(state="attached",timeout=12000)
            wait=min(30000,max(0,int(self.settings.get("wait_ms",1500))))
            if wait:
                page.wait_for_timeout(wait)
            html=page.content()
            if len(html.encode("utf-8")) > 2_000_000:
                raise ValueError("HTML-Seite zu gross")
            return extract(html,url)
        finally:
            page.close()

    def close(self):
        self.context.close()
        self.browser.close()
        self.playwright.stop()
