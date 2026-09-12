# Comparador de Precos de Supermercado

Compara precos entre os supermercados portugueses com loja online e descobre qual fica mais barato no total.

## Supermercados

| Supermercado | Scraping | Status |
|---|---|---|
| Continente | JS (Playwright) | Funcional |
| Pingo Doce | JS (Playwright) | Funcional |
| Auchan | HTTP | Funcional |

Supermercados sem loja online ou com bloqueios anti-bot foram removidos (Minipreco, Aldi, Lidl, Mercadona, Intermarche).

## Stack

- **Framework:** Flet (UI desktop)
- **Linguagem:** Python
- **Base de dados:** SQLite

## Funcionalidades

- Adicionar/editar/apagar produtos com categoria
- Registar precos por produto e supermercado (3 supermercados)
- Destaque automatico do supermercado mais barato por produto
- Resumo com total por supermercado e poupanca maxima
- Filtro por categoria e pesquisa
- Importacao automatica de produtos da **Lista de Compras**
- Tema escuro

## Instalacao

```bash
pip install -r requirements.txt
python -m playwright install chromium  # browser para scraping web
```

## Executar

```bash
python app.py
```

## Scraping de Precos Online

A app pesquisa automaticamente nos sites dos supermercados:

- **Cabaz Basico:** 28 produtos essenciais pre-definidos (leite, pao, ovos, arroz, massa, fruta, carne, etc.)
- **Raspar Todos:** pesquisa precos para todos os produtos ja adicionados
- Usa `requests` + `BeautifulSoup` para sites leves (Auchan)
- **Playwright** (Chromium) para sites com JavaScript (Continente, Pingo Doce)
- Progresso em tempo real na interface

O scraping depende da estrutura atual dos sites. Se os sites mudarem, os selectores CSS em `config.py` (`SCRAPER_SELECTORS`) precisam de ser actualizados.

## Integracao

Se existir `../Lista de Compras/shopping_list.db`, o botao de importacao carrega automaticamente os produtos de la.
