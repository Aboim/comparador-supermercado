import logging
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from config import (
    SUPERMERCADOS,
    SCRAPER_TIMEOUT,
    SCRAPER_MAX_RESULTS,
    SCRAPER_SELECTORS,
)

from scraper_common import extrair_resultados

logger = logging.getLogger(__name__)

_pw = None
_browser = None


def _get_playwright():
    global _pw
    if _pw is None:
        from playwright.sync_api import sync_playwright as _sp
        _pw = _sp
    return _pw


def _get_browser():
    global _browser
    if _browser is None:
        pw = _get_playwright()
        browser = pw().chromium.launch(headless=True)
        _browser = {
            "instance": pw(),
            "browser": browser,
        }
    return _browser["browser"]


def fechar_browser():
    global _browser, _pw
    if _browser:
        try:
            _browser["browser"].close()
        except Exception:
            pass
        try:
            _browser["instance"].stop()
        except Exception:
            pass
        _browser = None
    _pw = None


def raspar_supermercado_browser(sm_id, query, headless=True, max_results=SCRAPER_MAX_RESULTS):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("playwright nao instalado. pip install playwright && playwright install chromium")
        return []

    sm = next((s for s in SUPERMERCADOS if s["id"] == sm_id), None)
    if not sm:
        return []

    url = sm["url"].format(query=quote_plus(query))
    selectors_entry = SCRAPER_SELECTORS.get(sm_id)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
                locale="pt-PT",
            )
            page = context.new_page()
            page.set_default_timeout(SCRAPER_TIMEOUT * 1000)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except Exception:
                pass

            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            try:
                page.wait_for_timeout(2000)
            except Exception:
                pass

            html = page.content()
            context.close()
            browser.close()

        soup = BeautifulSoup(html, "lxml")
        return extrair_resultados(soup, sm_id, query, selectors_entry, max_results)

    except Exception as e:
        logger.error(f"Playwright {sm['nome']}: Erro: {e}")
        return []
