import re
import json
import logging
from urllib.parse import quote_plus

from config import (
    SUPERMERCADOS,
    SCRAPER_TIMEOUT,
    SCRAPER_MAX_RESULTS,
    SCRAPER_SELECTORS,
    SCRAPER_CATEGORIES,
    SCRAPER_GENERIC_PRICE_PATTERNS,
    SCRAPER_JSONLD_KEYWORDS,
)

logger = logging.getLogger(__name__)


def _limpar_preco(texto):
    if not texto:
        return None
    numeros = re.sub(r"[^\d,\.]", "", texto.strip())
    numeros = numeros.replace(",", ".")
    try:
        partes = numeros.split(".")
        if len(partes) > 1:
            numeros = "".join(partes[:-1]) + "." + partes[-1]
        return round(float(numeros), 2)
    except (ValueError, IndexError):
        return None


def _limpar_nome(texto):
    if not texto:
        return ""
    nome = " ".join(texto.strip().split())
    nome = re.sub(r'\s+', ' ', nome)
    return nome


def _classificar_categoria(nome):
    nome_lower = nome.lower()
    for categoria, palavras in SCRAPER_CATEGORIES.items():
        for palavra in palavras:
            if palavra in nome_lower:
                return categoria
    return "Mercearia"


def _extrair_jsonld(soup):
    resultados = []
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict):
                data = [data]
            if not isinstance(data, list):
                continue
            for item in data:
                if not isinstance(item, dict):
                    continue
                tipo = item.get("@type", "")
                if any(kw.lower() in str(tipo).lower() for kw in SCRAPER_JSONLD_KEYWORDS):
                    nome = item.get("name", "")
                    if not nome:
                        continue
                    oferta = item.get("offers", {})
                    if isinstance(oferta, list):
                        oferta = oferta[0] if oferta else {}
                    preco = oferta.get("price") if isinstance(oferta, dict) else None
                    if preco:
                        try:
                            preco_val = float(preco)
                            if 0.01 <= preco_val <= 500:
                                resultados.append({
                                    "nome": _limpar_nome(nome),
                                    "preco": preco_val,
                                    "unidade": "un",
                                    "categoria": _classificar_categoria(nome),
                                })
                        except (ValueError, TypeError):
                            pass
        except (json.JSONDecodeError, TypeError):
            continue
    return resultados


def _extrair_com_selectores(soup, selectors_entry, max_results):
    resultados = []
    if not selectors_entry:
        return resultados

    item_selector = selectors_entry.get("item", "")
    if not item_selector:
        return resultados

    try:
        items = soup.select(item_selector)
    except Exception:
        return resultados

    for item in items[:max_results * 3]:
        nome = None
        preco = None
        unidade = "un"

        for name_sel in [s.strip() for s in selectors_entry.get("name", "").split(",") if s.strip()]:
            try:
                elem = item.select_one(name_sel)
                if elem:
                    nome = _limpar_nome(elem.get_text())
                    if nome:
                        break
            except Exception:
                continue

        for price_sel in [s.strip() for s in selectors_entry.get("price", "").split(",") if s.strip()]:
            try:
                elem = item.select_one(price_sel)
                if elem:
                    preco = _limpar_preco(elem.get_text())
                    if preco and preco > 0:
                        break
            except Exception:
                continue

        for unit_sel in [s.strip() for s in selectors_entry.get("unit", "").split(",") if s.strip()]:
            try:
                elem = item.select_one(unit_sel)
                if elem:
                    unidade = _limpar_nome(elem.get_text()) or "un"
                    break
            except Exception:
                continue

        if nome and preco and 0.01 <= preco <= 500:
            resultados.append({
                "nome": nome,
                "preco": preco,
                "unidade": unidade,
                "categoria": _classificar_categoria(nome),
            })

        if len(resultados) >= max_results:
            break

    return resultados


def _extrair_regex_fallback(soup, query, max_results):
    resultados = []
    texto = soup.get_text(separator=" ", strip=True)

    precos_brutos = re.findall(r'(\d+[.,]\d{2})\s*€', texto)
    if not precos_brutos:
        precos_brutos = re.findall(r'€\s*(\d+[.,]\d{2})', texto)
    if not precos_brutos:
        precos_brutos = re.findall(r'(\d+[.,]\d{2})', texto)

    precos_validos = []
    for p in precos_brutos:
        preco = _limpar_preco(p)
        if preco and 0.01 <= preco <= 500:
            precos_validos.append(preco)

    if not precos_validos:
        return resultados

    noise_words = {
        "skip", "main", "content", "resultado", "pesquisa", "online", "aceitar",
        "cookie", "cookies", "navegar", "continuar", "login", "registo", "registe",
        "menu", "footer", "header", "breadcrumb", "search", "encontrado", "encontrados",
        "produto", "produtos", "carrinho", "compras", "favorito", "wishlist",
        "subscrever", "newsletter", "promocao", "promocoes", "folheto",
        "loja", "lojas", "contacto", "contactos", "ajuda", "sobre", "politica",
        "privacidade", "termos", "condicoes",
    }

    linhas = texto.split("\n")
    for linha in linhas:
        linha_limpa = linha.strip()
        if len(linha_limpa) < 5:
            continue

        preco_str = re.search(r'(\d+[.,]\d{2})', linha_limpa)
        if not preco_str:
            continue
        preco = _limpar_preco(preco_str.group(1))
        if preco not in precos_validos:
            continue

        nome_tmp = re.sub(r'\d+[.,]\d{2}\s*€?', '', linha_limpa)
        nome_tmp = re.sub(r'[^\w\s%\-]', ' ', nome_tmp)
        nome_tmp = _limpar_nome(nome_tmp)

        palavras = set(nome_tmp.lower().split())
        if len(palavras) <= 1:
            continue
        if any(w in noise_words for w in palavras):
            continue
        if len(nome_tmp) < 5 or len(nome_tmp) > 80:
            continue
        if nome_tmp.lower() in noise_words:
            continue

        resultados.append({
            "nome": nome_tmp[:80],
            "preco": preco,
            "unidade": "un",
            "categoria": _classificar_categoria(nome_tmp),
        })

        if len(resultados) >= max_results:
            break

    if not resultados and precos_validos:
        resultados.append({
            "nome": query.title(),
            "preco": precos_validos[0],
            "unidade": "un",
            "categoria": _classificar_categoria(query),
        })

    return resultados


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
    resultados = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page()
            page.set_default_timeout(SCRAPER_TIMEOUT * 1000)
            page.goto(url, wait_until="domcontentloaded")

            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            html = page.content()
            browser.close()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # 1) Tentar extrair JSON-LD
        resultados = _extrair_jsonld(soup)
        if resultados:
            return resultados[:max_results]

        # 2) Tentar selectores CSS
        selectors_entry = SCRAPER_SELECTORS.get(sm_id)
        if selectors_entry:
            resultados = _extrair_com_selectores(soup, selectors_entry, max_results)

        # 3) Fallback regex
        if not resultados:
            resultados = _extrair_regex_fallback(soup, query, max_results)

    except Exception as e:
        logger.error(f"Playwright {sm['nome']}: Erro: {e}")

    return resultados
