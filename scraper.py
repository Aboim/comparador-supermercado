import asyncio
import logging
import random
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
)

from scraper_common import (
    extrair_resultados,
)

logger = logging.getLogger(__name__)

_session = None
_aio_session = None

MAX_RETRIES = 2
RATE_LIMIT_MIN = 0.6
RATE_LIMIT_MAX = 1.2


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
                "Accept-Encoding": "gzip, deflate",
            },
            timeout=timeout,
        )
    return _aio_session


async def _rate_limit():
    await asyncio.sleep(random.uniform(RATE_LIMIT_MIN, RATE_LIMIT_MAX))


async def _raspar_supermercado_http_async(sm_id, query, max_results=SCRAPER_MAX_RESULTS):
    sm = next((s for s in SUPERMERCADOS if s["id"] == sm_id), None)
    if not sm:
        return []

    url = sm["url"].format(query=quote_plus(query))
    selectors_entry = SCRAPER_SELECTORS.get(sm_id)

    for attempt in range(MAX_RETRIES + 1):
        try:
            session = await _get_aiohttp_session()
            async with session.get(url, allow_redirects=True) as resp:
                if resp.status != 200:
                    logger.warning(f"{sm['nome']}: HTTP {resp.status}")
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(1 + attempt)
                        continue
                    return []
                html = await resp.text()

            soup = BeautifulSoup(html, "lxml")
            resultados = extrair_resultados(soup, sm_id, query, selectors_entry, max_results)

            if resultados:
                return resultados
            if attempt < MAX_RETRIES:
                await asyncio.sleep(1 + attempt)

        except asyncio.TimeoutError:
            logger.warning(f"{sm['nome']}: Timeout (tentativa {attempt + 1})")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(1 + attempt)
        except aiohttp.ClientError as e:
            logger.warning(f"{sm['nome']}: Erro de conexao: {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2 + attempt)
        except Exception as e:
            logger.error(f"{sm['nome']}: Erro: {e}")
            break

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

    await _rate_limit()
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

import time

def raspar_supermercado_simples(sm_id, query, max_results=SCRAPER_MAX_RESULTS):
    sm = next((s for s in SUPERMERCADOS if s["id"] == sm_id), None)
    if not sm:
        return []

    url = sm["url"].format(query=quote_plus(query))
    selectors_entry = SCRAPER_SELECTORS.get(sm_id)

    for attempt in range(MAX_RETRIES + 1):
        try:
            session = _get_session()
            resp = session.get(url, timeout=SCRAPER_TIMEOUT, allow_redirects=True)
            if resp.status_code != 200:
                logger.warning(f"{sm['nome']}: HTTP {resp.status_code}")
                if attempt < MAX_RETRIES:
                    time.sleep(1 + attempt)
                    continue
                return []

            soup = BeautifulSoup(resp.text, "lxml")
            resultados = extrair_resultados(soup, sm_id, query, selectors_entry, max_results)
            if resultados:
                return resultados
            if attempt < MAX_RETRIES:
                time.sleep(1 + attempt)

        except requests.Timeout:
            logger.warning(f"{sm['nome']}: Timeout")
            if attempt < MAX_RETRIES:
                time.sleep(1 + attempt)
        except requests.ConnectionError:
            logger.warning(f"{sm['nome']}: Erro de conexao")
            if attempt < MAX_RETRIES:
                time.sleep(2 + attempt)
        except Exception as e:
            logger.error(f"{sm['nome']}: Erro: {e}")
            break

    return []


def raspar_supermercado(sm_id, query, max_results=SCRAPER_MAX_RESULTS):
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
    total_sm = len(SUPERMERCADOS)
    resultado = {"query": query, "precos": {}}

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
