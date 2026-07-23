import re
import json
import time
import asyncio
import logging
from urllib.parse import quote_plus

import aiohttp
import requests
from bs4 import BeautifulSoup

import database as db

from config import (
    SUPERMERCADOS,
    CABAZ_BASICO,
    SCRAPER_TIMEOUT,
    SCRAPER_MAX_RESULTS,
    SCRAPER_USER_AGENT,
    SCRAPER_SELECTORS,
    SCRAPER_CATEGORIES,
    SCRAPER_GENERIC_PRICE_PATTERNS,
    SCRAPER_JSONLD_KEYWORDS,
)

logger = logging.getLogger(__name__)

_session = None
_aio_session = None


def _get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": SCRAPER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
        })
    return _session


async def _get_aiohttp_session():
    global _aio_session
    if _aio_session is None:
        timeout = aiohttp.ClientTimeout(total=SCRAPER_TIMEOUT)
        _aio_session = aiohttp.ClientSession(
            headers={
                "User-Agent": SCRAPER_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
            },
            timeout=timeout,
        )
    return _aio_session


def _limpar_preco(texto):
    if not texto:
        return None
    numeros = re.sub(r"[^\d,\.]", "", texto.strip())
    numeros = numeros.replace(",", ".")
    try:
        partes = numeros.split(".")
        if len(partes) > 1:
            numeros = "".join(partes[:-1]) + "." + partes[-1]
        valor = round(float(numeros), 2)
        return valor
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


def _relevancia_match(nome_produto, query):
    nome = nome_produto.lower()
    termos = query.lower().split()
    score = sum(1 for t in termos if t in nome)
    return score


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

    # Encontrar todos os precos em formato EUR
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

    # Palavras de lixo para filtrar
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

        # Limpar nome: remover precos e caracteres especiais
        nome_tmp = re.sub(r'\d+[.,]\d{2}\s*€?', '', linha_limpa)
        nome_tmp = re.sub(r'[^\w\s%\-]', ' ', nome_tmp)
        nome_tmp = _limpar_nome(nome_tmp)

        # Filtrar lixo
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

    # Se o fallback regex nao produziu nomes validos, usar a query
    if not resultados and precos_validos:
        resultados.append({
            "nome": query.title(),
            "preco": precos_validos[0],
            "unidade": "un",
            "categoria": _classificar_categoria(query),
        })

    return resultados


# ---------------------------------------------------------------------------
#  ASYNC implementations (aiohttp) — preferidas
# ---------------------------------------------------------------------------

async def _raspar_supermercado_http_async(sm_id, query, max_results=SCRAPER_MAX_RESULTS):
    sm = next((s for s in SUPERMERCADOS if s["id"] == sm_id), None)
    if not sm:
        return []

    url = sm["url"].format(query=quote_plus(query))

    try:
        session = await _get_aiohttp_session()
        async with session.get(url, allow_redirects=True) as resp:
            if resp.status != 200:
                logger.warning(f"{sm['nome']}: HTTP {resp.status}")
                return []
            html = await resp.text()

        soup = BeautifulSoup(html, "lxml")

        resultados = _extrair_jsonld(soup)
        if resultados:
            return resultados[:max_results]

        selectors_entry = SCRAPER_SELECTORS.get(sm_id)
        if selectors_entry:
            resultados = _extrair_com_selectores(soup, selectors_entry, max_results)

        if not resultados:
            resultados = _extrair_regex_fallback(soup, query, max_results)

        return resultados

    except asyncio.TimeoutError:
        logger.warning(f"{sm['nome']}: Timeout")
    except aiohttp.ClientError as e:
        logger.warning(f"{sm['nome']}: Erro de conexao: {e}")
    except Exception as e:
        logger.error(f"{sm['nome']}: Erro: {e}")

    return []


async def raspar_supermercado_async(sm_id, query, max_results=SCRAPER_MAX_RESULTS):
    cached = db.get_cache(sm_id, query)
    if cached:
        logger.info(f"Cache hit: {sm_id}/{query}")
        return cached[:max_results]

    sm = next((s for s in SUPERMERCADOS if s["id"] == sm_id), None)
    nome_sm = sm["nome"] if sm else sm_id

    resultados = await _raspar_supermercado_http_async(sm_id, query, max_results)

    if not resultados:
        logger.info(f"{nome_sm}: HTTP sem resultados, a tentar browser...")
        try:
            from scraper_playwright import raspar_supermercado_browser
            resultados = await asyncio.to_thread(
                raspar_supermercado_browser, sm_id, query, True, max_results
            )
        except ImportError:
            logger.info(f"{nome_sm}: Playwright nao disponivel.")
        except Exception as e:
            logger.error(f"{nome_sm}: Erro Playwright: {e}")

    if resultados:
        db.set_cache(sm_id, query, resultados)

    return resultados


async def raspar_produto_comum_async(query, callback=None):
    total_sm = len(SUPERMERCADOS)
    resultado = {"query": query, "precos": {}}

    async def scrape_single_store(sm, idx):
        sm_id = sm["id"]
        if callback:
            callback(
                sm=sm["nome"],
                produto=query,
                termo=query,
                progresso=f"{idx + 1}/{total_sm}",
            )
        resultados = await raspar_supermercado_async(sm_id, query, max_results=5)
        return sm_id, resultados

    tasks = [scrape_single_store(sm, i) for i, sm in enumerate(SUPERMERCADOS)]
    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    for item in all_results:
        if isinstance(item, BaseException):
            continue
        sm_id, resultados = item
        if resultados:
            resultados.sort(key=lambda x: x["preco"])
            r = resultados[0]
            if 0.01 <= r["preco"] <= 500:
                resultado["precos"][sm_id] = {
                    "preco": r["preco"],
                    "nome": r.get("nome", query),
                    "unidade": r.get("unidade", "un"),
                }

    if callback:
        callback(sm="", produto=query, termo="", progresso="Concluido")

    return resultado


async def raspar_cabaz_basico_async(callback=None):
    total_produtos = len(CABAZ_BASICO)
    resultados_cabaz = []

    for i, produto in enumerate(CABAZ_BASICO):
        item = {
            "nome": produto["nome"],
            "categoria": produto["categoria"],
            "unidade": produto["unidade"],
            "precos": {},
        }
        termos = produto["termos_pesquisa"]

        async def scrape_store_for_cabaz(sm):
            sm_id = sm["id"]
            preco_encontrado = None
            nome_encontrado = None

            for termo in termos:
                if callback:
                    callback(
                        sm=sm["nome"],
                        produto=produto["nome"],
                        termo=termo,
                        progresso=f"{i + 1}/{total_produtos}",
                    )
                resultados = await raspar_supermercado_async(sm_id, termo, max_results=5)
                if resultados:
                    resultados.sort(key=lambda x: x["preco"])
                    r = resultados[0]
                    if 0.01 <= r["preco"] <= 200:
                        preco_encontrado = r["preco"]
                        nome_encontrado = r.get("nome", produto["nome"])
                        break
                await asyncio.sleep(0.5)

            return sm_id, preco_encontrado, nome_encontrado

        tasks = [scrape_store_for_cabaz(sm) for sm in SUPERMERCADOS]
        store_results = await asyncio.gather(*tasks, return_exceptions=True)

        for item_result in store_results:
            if isinstance(item_result, BaseException):
                continue
            sm_id, preco_enc, nome_enc = item_result
            if preco_enc:
                item["precos"][sm_id] = {
                    "preco": preco_enc,
                    "nome": nome_enc or produto["nome"],
                }

        if item["precos"]:
            resultados_cabaz.append(item)

    return resultados_cabaz


async def raspar_todos_produtos_async(produtos, callback=None):
    resultados = {}
    total = len(produtos)

    for i, p in enumerate(produtos):
        pid = p["id"]
        nome = p["nome"]

        async def scrape_store(sm):
            sm_id = sm["id"]
            if callback:
                callback(
                    sm=sm["nome"],
                    produto=nome,
                    termo=nome,
                    progresso=f"{i + 1}/{total}",
                )
            res = await raspar_supermercado_async(sm_id, nome, max_results=5)
            return sm_id, res

        tasks = [scrape_store(sm) for sm in SUPERMERCADOS]
        store_results = await asyncio.gather(*tasks, return_exceptions=True)

        for item_result in store_results:
            if isinstance(item_result, BaseException):
                continue
            sm_id, res = item_result
            if res:
                res.sort(key=lambda x: x["preco"])
                r = res[0]
                if 0.01 <= r["preco"] <= 500:
                    resultados.setdefault(pid, {})[sm_id] = r["preco"]

        await asyncio.sleep(0.4)

    return resultados


# ---------------------------------------------------------------------------
#  SYNC implementations (requests) — deprecated, kept for backwards compat
# ---------------------------------------------------------------------------

def raspar_supermercado_simples(sm_id, query, max_results=SCRAPER_MAX_RESULTS):
    # DEPRECATED: use raspar_supermercado_async instead
    sm = next((s for s in SUPERMERCADOS if s["id"] == sm_id), None)
    if not sm:
        return []

    url = sm["url"].format(query=quote_plus(query))
    resultados = []

    try:
        session = _get_session()
        resp = session.get(url, timeout=SCRAPER_TIMEOUT, allow_redirects=True)
        if resp.status_code != 200:
            logger.warning(f"{sm['nome']}: HTTP {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")

        # 1) Tentar extrair JSON-LD
        resultados = _extrair_jsonld(soup)
        if resultados:
            resultados = resultados[:max_results]
            return resultados

        # 2) Tentar selectores CSS
        selectors_entry = SCRAPER_SELECTORS.get(sm_id)
        if selectors_entry:
            resultados = _extrair_com_selectores(soup, selectors_entry, max_results)

        # 3) Fallback regex
        if not resultados:
            resultados = _extrair_regex_fallback(soup, query, max_results)

    except requests.Timeout:
        logger.warning(f"{sm['nome']}: Timeout")
    except requests.ConnectionError:
        logger.warning(f"{sm['nome']}: Erro de conexao")
    except Exception as e:
        logger.error(f"{sm['nome']}: Erro: {e}")

    return resultados


def raspar_supermercado(sm_id, query, max_results=SCRAPER_MAX_RESULTS):
    # DEPRECATED: use raspar_supermercado_async instead
    sm = next((s for s in SUPERMERCADOS if s["id"] == sm_id), None)
    if not sm:
        return []

    resultados = raspar_supermercado_simples(sm_id, query, max_results)

    if not resultados:
        logger.info(f"{sm['nome']}: HTTP sem resultados, a tentar browser...")
        try:
            from scraper_playwright import raspar_supermercado_browser
            resultados = raspar_supermercado_browser(sm_id, query, headless=True, max_results=max_results)
        except ImportError:
            logger.info(f"{sm['nome']}: Playwright nao disponivel.")
        except Exception as e:
            logger.error(f"{sm['nome']}: Erro Playwright: {e}")

    return resultados


def raspar_produto_comum(query, callback=None):
    # DEPRECATED: use raspar_produto_comum_async instead
    total_sm = len(SUPERMERCADOS)
    resultado = {
        "query": query,
        "precos": {},
    }

    for i, sm in enumerate(SUPERMERCADOS):
        sm_id = sm["id"]
        if callback:
            callback(
                sm=sm["nome"],
                produto=query,
                termo=query,
                progresso=f"{i + 1}/{total_sm}",
            )

        resultados = raspar_supermercado(sm_id, query, max_results=5)
        if resultados:
            resultados.sort(key=lambda x: x["preco"])
            r = resultados[0]
            if 0.01 <= r["preco"] <= 500:
                resultado["precos"][sm_id] = {
                    "preco": r["preco"],
                    "nome": r.get("nome", query),
                    "unidade": r.get("unidade", "un"),
                }
            time.sleep(0.3)
        else:
            time.sleep(0.3)

    if callback:
        callback(sm="", produto=query, termo="", progresso="Concluido")

    return resultado


def raspar_cabaz_basico(callback=None):
    # DEPRECATED: use raspar_cabaz_basico_async instead
    total_produtos = len(CABAZ_BASICO)
    resultados_cabaz = []

    for i, produto in enumerate(CABAZ_BASICO):
        item = {
            "nome": produto["nome"],
            "categoria": produto["categoria"],
            "unidade": produto["unidade"],
            "precos": {},
        }

        termos = produto["termos_pesquisa"]

        for sm in SUPERMERCADOS:
            sm_id = sm["id"]
            preco_encontrado = None
            nome_encontrado = None

            for termo in termos:
                if callback:
                    callback(
                        sm=sm["nome"],
                        produto=produto["nome"],
                        termo=termo,
                        progresso=f"{i + 1}/{total_produtos}",
                    )
                resultados = raspar_supermercado(sm_id, termo, max_results=5)
                if resultados:
                    resultados.sort(key=lambda x: x["preco"])
                    r = resultados[0]
                    if 0.01 <= r["preco"] <= 200:
                        preco_encontrado = r["preco"]
                        nome_encontrado = r.get("nome", produto["nome"])
                        break

                time.sleep(0.5)

            if preco_encontrado:
                item["precos"][sm_id] = {
                    "preco": preco_encontrado,
                    "nome": nome_encontrado or produto["nome"],
                }

        if item["precos"]:
            resultados_cabaz.append(item)

    return resultados_cabaz


def raspar_todos_produtos(produtos, callback=None):
    # DEPRECATED: use raspar_todos_produtos_async instead
    resultados = {}
    total = len(produtos)

    for i, p in enumerate(produtos):
        pid = p["id"]
        nome = p["nome"]

        for sm in SUPERMERCADOS:
            sm_id = sm["id"]
            if callback:
                callback(sm=sm["nome"], produto=nome, termo=nome, progresso=f"{i + 1}/{total}")
            res = raspar_supermercado(sm_id, nome, max_results=5)
            if res:
                res.sort(key=lambda x: x["preco"])
                r = res[0]
                if 0.01 <= r["preco"] <= 500:
                    resultados.setdefault(pid, {})[sm_id] = r["preco"]
            time.sleep(0.4)

    return resultados
