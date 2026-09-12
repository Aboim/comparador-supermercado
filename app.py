import asyncio
import logging
import flet as ft
import database as db
import scraper
from config import COLORS, SUPERMERCADOS, CATEGORIAS

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def _border(color):
    s = ft.border.BorderSide(1, color)
    return ft.border.Border(top=s, bottom=s, left=s, right=s)


def main(page: ft.Page):
    page.title = "Comparador de Precos"
    page.bgcolor = COLORS["bg"]
    page.padding = 24
    page.window.width = 1100
    page.window.height = 800
    page.window.min_width = 800
    page.window.min_height = 500
    page.window.center = True
    page.fonts = {"Outfit": "https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap"}
    page.theme = ft.Theme(font_family="Outfit")

    db.init_db()

    supermercado_map = {s["id"]: s for s in SUPERMERCADOS}
    produto_selecionado = None
    categoria_filtro = "Todas"
    scraping_lock = asyncio.Lock()

    produto_lista = ft.ListView(expand=True, spacing=4, padding=0)
    preco_inputs_container = ft.Column(spacing=8)
    resumo_container = ft.Column(spacing=8)
    scraper_progress = ft.ProgressBar(width=300, value=0, visible=False, bgcolor=COLORS["card_border"], color=COLORS["blue"])
    sm_name_to_id = {s["nome"]: s["id"] for s in SUPERMERCADOS}

    # Painel de progresso por supermercado
    progress_sm_rows = {}
    for sm in SUPERMERCADOS:
        sm_icon = ft.Icon(ft.Icons.HOURGLASS_EMPTY, size=14, color=COLORS["text_dim"])
        sm_name = ft.Text(sm["nome"], size=11, width=90, color=COLORS["text_dim"])
        sm_status = ft.Text("--", size=11, color=COLORS["text_dim"], expand=True)
        sm_price = ft.Text("", size=11, weight="bold", color=COLORS["text_dim"])
        sm_row = ft.Row([sm_icon, sm_name, sm_status, sm_price], spacing=6, alignment=ft.MainAxisAlignment.START)
        progress_sm_rows[sm["id"]] = {"row": sm_row, "icon": sm_icon, "status": sm_status, "price": sm_price}

    progress_header = ft.Text("", size=12, weight="bold", color=COLORS["white"])
    progress_panel = ft.Column(
        [progress_header] + [r["row"] for r in progress_sm_rows.values()],
        spacing=3,
    )
    progress_container = ft.Container(
        content=progress_panel,
        bgcolor=COLORS["bg"],
        border_radius=8,
        padding=10,
        visible=False,
    )

    def _init_progress(titulo):
        progress_header.value = titulo
        progress_container.visible = True
        for sm_id, row in progress_sm_rows.items():
            row["icon"].name = ft.Icons.HOURGLASS_EMPTY
            row["icon"].color = COLORS["text_dim"]
            row["status"].value = "À espera"
            row["status"].color = COLORS["text_dim"]
            row["price"].value = ""
            row["price"].color = COLORS["text_dim"]
        page.update()

    def _finish_progress():
        scraper_progress.visible = False
        page.update()

    def _update_sm_progress(sm_nome, estado_texto, preco=None, icon=None, cor=None):
        sm_id = sm_name_to_id.get(sm_nome)
        if not sm_id:
            return
        row = progress_sm_rows.get(sm_id)
        if not row:
            return
        if icon:
            row["icon"].name = icon
        row["icon"].color = cor or COLORS["blue"]
        row["status"].value = estado_texto
        row["status"].color = cor or COLORS["white"]
        if preco is not None:
            row["price"].value = f"{preco:.2f}€"
            row["price"].color = cor or COLORS["green"]
        else:
            row["price"].value = "--"
            row["price"].color = COLORS["text_dim"]
        page.update()

    def montar_resumo():
        comp = db.obter_comparativo()
        resumo_container.controls.clear()
        if not comp:
            resumo_container.controls.append(
                ft.Text("Adiciona produtos e precos para ver o comparativo.", size=13, color=COLORS["text_dim"])
            )
        else:
            melhor = comp[0]
            nome_melhor = supermercado_map.get(melhor["supermercado_id"], {}).get("nome", melhor["supermercado_id"])
            resumo_container.controls.append(
                ft.Row([
                    ft.Icon(ft.Icons.STAR, color=COLORS["gold"], size=18),
                    ft.Text(f"Mais barato: {nome_melhor} — {melhor['total']}€ ({melhor['itens']} itens)", size=14, weight="bold", color=COLORS["gold"]),
                ])
            )
            if len(comp) > 1:
                diff = round(comp[-1]["total"] - melhor["total"], 2)
                if diff > 0:
                    resumo_container.controls.append(
                        ft.Text(f"Poupanca maxima: {diff}€", size=12, color=COLORS["green"])
                    )
            for row in comp:
                nome = supermercado_map.get(row["supermercado_id"], {}).get("nome", row["supermercado_id"])
                resumo_container.controls.append(
                    ft.Row([
                        ft.Text(nome, size=12, color=COLORS["text_dim"]),
                        ft.Text(f"{row['total']}€", size=12, weight="bold", color=COLORS["white"]),
                        ft.Text(f"({row['itens']} itens)", size=11, color=COLORS["text_dim"]),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                )
        page.update()

    def montar_preco_inputs(produto):
        preco_inputs_container.controls.clear()
        if not produto:
            preco_inputs_container.controls.append(
                ft.Text("Seleciona um produto para editar precos.", size=13, color=COLORS["text_dim"])
            )
            page.update()
            return

        precos_existentes = db.obter_precos_por_produto(produto["id"])
        precos_map = {p["supermercado_id"]: p["preco"] for p in precos_existentes}

        preco_inputs_container.controls.append(
            ft.Text(f"Precos: {produto['nome']}", size=14, weight="bold", color=COLORS["white"])
        )
        preco_inputs_container.controls.append(ft.Divider(height=1, color=COLORS["card_border"]))

        mais_barato = min(precos_existentes, key=lambda x: x["preco"]) if precos_existentes else None
        for sm in SUPERMERCADOS:
            preco_atual = precos_map.get(sm["id"], None)
            campo = ft.TextField(
                value=str(preco_atual) if preco_atual is not None else "",
                label=sm["nome"],
                hint_text="0.00",
                keyboard_type=ft.KeyboardType.NUMBER,
                border_radius=8,
                bgcolor=COLORS["card_bg"],
                border_color=COLORS["card_border"],
                text_size=14,
                content_padding=ft.padding.Padding(12, 8, 12, 8),
                dense=True,
            )
            campo.sm_id = sm["id"]

            def salvar_preco(e, sm_id=sm["id"], pid=produto["id"]):
                val = e.control.value.strip()
                if val == "":
                    db.remover_preco(pid, sm_id)
                else:
                    try:
                        preco_val = round(float(val.replace(",", ".")), 2)
                        db.atualizar_preco(pid, sm_id, preco_val)
                    except ValueError:
                        page.snack_bar = ft.SnackBar(ft.Text("Preco invalido"), bgcolor=COLORS["red"])
                        page.snack_bar.open = True
                        page.update()
                        return
                montar_preco_inputs(produto)
                montar_resumo()
                carregar_produtos()

            campo.on_submit = salvar_preco
            campo.on_blur = salvar_preco

            destaque = mais_barato and mais_barato["supermercado_id"] == sm["id"]
            row = ft.Row(
                [
                    ft.Text(sm["nome"], size=12, width=100, color=COLORS["gold"] if destaque else COLORS["text_dim"]),
                    campo,
                    ft.Text("€" if preco_atual else "", size=12, color=COLORS["text_dim"], width=30),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.START,
            )
            preco_inputs_container.controls.append(row)
        page.update()

    def selecionar_produto(produto):
        nonlocal produto_selecionado
        produto_selecionado = produto
        montar_preco_inputs(produto)
        carregar_produtos()

    def carregar_produtos(pesquisa=None):
        produtos = db.listar_produtos(
            categoria=None if categoria_filtro == "Todas" else categoria_filtro,
            pesquisa=pesquisa,
        )
        produto_lista.controls.clear()
        for p in produtos:
            is_selected = produto_selecionado and produto_selecionado["id"] == p["id"]
            precos = db.obter_precos_por_produto(p["id"])
            n_precos = len(precos)
            min_preco = f"{min(pr['preco'] for pr in precos):.2f}€" if precos else "--"

            tile = ft.Container(
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(p["nome"], size=14, weight="bold", color=COLORS["white"]),
                                ft.Text(p["categoria"], size=11, color=COLORS["text_dim"]),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.Text(f"{n_precos} precos", size=11, color=COLORS["text_dim"]),
                        ft.Text(min_preco, size=13, weight="bold", color=COLORS["green"]),
                    ],
                    spacing=12,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=ft.padding.Padding(12, 10, 12, 10),
                border_radius=10,
                bgcolor=COLORS["blue"] + "22" if is_selected else COLORS["card_bg"],
                border=_border(COLORS["blue"] if is_selected else COLORS["card_border"]),
                on_click=lambda e, prod=p: selecionar_produto(prod),
            )
            produto_lista.controls.append(tile)
        page.update()

    def adicionar_produto_dialog(e):
        nome_field = ft.TextField(
            label="Nome do produto",
            border_radius=8,
            bgcolor=COLORS["card_bg"],
            border_color=COLORS["card_border"],
            text_size=14,
            autofocus=True,
        )
        cat_dropdown = ft.Dropdown(
            label="Categoria",
            options=[ft.dropdown.Option(c) for c in CATEGORIAS],
            value=CATEGORIAS[0],
            border_radius=8,
            bgcolor=COLORS["card_bg"],
            border_color=COLORS["card_border"],
            text_size=14,
        )

        def confirmar(e):
            nome = nome_field.value.strip()
            if not nome:
                return
            pid = db.adicionar_produto(nome, cat_dropdown.value, "un")
            page.pop_dialog()
            carregar_produtos()
            novo = {"id": pid, "nome": nome, "categoria": cat_dropdown.value, "unidade": "un"}
            selecionar_produto(novo)

        dialog = ft.AlertDialog(
            title=ft.Text("Adicionar Produto", size=16, weight="bold", color=COLORS["white"]),
            content=ft.Column([nome_field, cat_dropdown], spacing=12, width=350),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
                ft.Button(content=ft.Text("Adicionar"), on_click=confirmar),
            ],
            bgcolor=COLORS["card_bg"],
        )
        page.show_dialog(dialog)

    def importar_lista(e):
        count = db.importar_lista_compras()
        if count > 0:
            msg = f"Importados {count} produtos da Lista de Compras."
            cor = COLORS["green"]
        elif count == 0:
            msg = "Nenhum produto novo para importar."
            cor = COLORS["text_dim"]
        else:
            msg = "Erro ao importar. A base de dados da Lista de Compras existe?"
            cor = COLORS["red"]
        page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=cor)
        page.snack_bar.open = True
        carregar_produtos()
        page.update()

    def apagar_produto(e):
        if not produto_selecionado:
            return
        pid = produto_selecionado["id"]
        nome = produto_selecionado["nome"]

        def confirmar(e):
            db.remover_produto(pid)
            nonlocal produto_selecionado
            produto_selecionado = None
            page.pop_dialog()
            montar_preco_inputs(None)
            montar_resumo()
            carregar_produtos()

        dialog = ft.AlertDialog(
            title=ft.Text(f"Apagar {nome}?", size=16, color=COLORS["white"]),
            content=ft.Text("Isto remove o produto e todos os precos associados.", size=13, color=COLORS["text_dim"]),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
                ft.Button(content=ft.Text("Apagar", color=COLORS["red"]), on_click=confirmar),
            ],
            bgcolor=COLORS["card_bg"],
        )
        page.show_dialog(dialog)

    def filtrar_categoria(e):
        nonlocal categoria_filtro
        categoria_filtro = e.control.value
        carregar_produtos()

    # ---- SCRAPER ----

    def _atualiza_status(sm, produto, termo, progresso):
        progress_header.value = f"{progresso} — {produto}"
        _update_sm_progress(sm, f"Pesquisando '{termo}'...", icon=ft.Icons.SYNC, cor=COLORS["blue"])
        page.update()

    def raspar_cabaz(e):
        if scraping_lock.locked():
            page.snack_bar = ft.SnackBar(ft.Text("Raspagem ja em curso."), bgcolor=COLORS["text_dim"])
            page.snack_bar.open = True
            page.update()
            return
        page.run_task(_raspar_cabaz_async)

    async def _raspar_cabaz_async():
        nonlocal scraping_lock
        async with scraping_lock:
            btn_cabaz.disabled = True
            btn_raspar_todos.disabled = True
            scraper_progress.visible = True
            _init_progress("A raspar Cabaz Basico...")
            page.update()

            try:
                db.adicionar_cabaz_basico()
                resultados = await scraper.raspar_cabaz_basico_async(callback=_atualiza_status)

                for sm in SUPERMERCADOS:
                    melhor = None
                    for item in resultados:
                        if sm["id"] in item["precos"]:
                            dados = item["precos"][sm["id"]]
                            if melhor is None or dados["preco"] < melhor:
                                melhor = dados["preco"]
                    if melhor:
                        _update_sm_progress(sm["nome"], f"{len([i for i in resultados if sm['id'] in i['precos']])} produtos", preco=melhor, icon=ft.Icons.CHECK_CIRCLE, cor=COLORS["green"])
                    else:
                        _update_sm_progress(sm["nome"], "Sem resultados", icon=ft.Icons.ERROR, cor=COLORS["red"])

                count = db.atualizar_precos_em_massa(resultados)

                progress_header.value = f"Concluido! {count} precos de {len(resultados)} produtos."
                scraper_progress.value = 1
                page.update()

                page.snack_bar = ft.SnackBar(
                    ft.Text(f"Raspagem concluida: {len(resultados)} produtos, {count} precos."),
                    bgcolor=COLORS["green"],
                )
                page.snack_bar.open = True
            except Exception as ex:
                progress_header.value = f"Erro: {ex}"
                page.snack_bar = ft.SnackBar(ft.Text(f"Erro na raspagem: {ex}"), bgcolor=COLORS["red"])
                page.snack_bar.open = True
            finally:
                btn_cabaz.disabled = False
                btn_raspar_todos.disabled = False
                scraper_progress.visible = False
                montar_resumo()
                carregar_produtos()
                page.update()

    def raspar_todos_produtos(e):
        if scraping_lock.locked():
            page.snack_bar = ft.SnackBar(ft.Text("Raspagem ja em curso."), bgcolor=COLORS["text_dim"])
            page.snack_bar.open = True
            page.update()
            return
        produtos = db.listar_produtos()
        if not produtos:
            db.adicionar_cabaz_basico()
            produtos = db.listar_produtos()

        page.run_task(_raspar_todos_produtos_async, produtos)

    async def _raspar_todos_produtos_async(produtos):
        nonlocal scraping_lock
        async with scraping_lock:
            btn_cabaz.disabled = True
            btn_raspar_todos.disabled = True
            btn_comparar.disabled = True
            scraper_progress.visible = True
            _init_progress(f"A raspar {len(produtos)} produtos...")
            page.update()

            try:
                precos = await scraper.raspar_todos_produtos_async(produtos, callback=_atualiza_status)
                count = db.atualizar_precos_por_scraper(precos)

                for sm in SUPERMERCADOS:
                    sm_count = sum(1 for pid_precos in precos.values() if sm["id"] in pid_precos)
                    if sm_count:
                        _update_sm_progress(sm["nome"], f"{sm_count} precos", icon=ft.Icons.CHECK_CIRCLE, cor=COLORS["green"])
                    else:
                        _update_sm_progress(sm["nome"], "Sem resultados", icon=ft.Icons.ERROR, cor=COLORS["red"])

                scraper_progress.value = 1
                progress_header.value = f"Concluido! {count} precos actualizados."
                page.update()

                page.snack_bar = ft.SnackBar(
                    ft.Text(f"Raspagem concluida: {count} precos encontrados."),
                    bgcolor=COLORS["green"],
                )
                page.snack_bar.open = True
            except Exception as ex:
                progress_header.value = f"Erro: {ex}"
                for sm in SUPERMERCADOS:
                    _update_sm_progress(sm["nome"], "Erro", icon=ft.Icons.ERROR, cor=COLORS["red"])
                page.snack_bar = ft.SnackBar(ft.Text(f"Erro na raspagem: {ex}"), bgcolor=COLORS["red"])
                page.snack_bar.open = True
                logger.error(f"Erro raspar todos: {ex}", exc_info=True)
            finally:
                btn_cabaz.disabled = False
                btn_raspar_todos.disabled = False
                btn_comparar.disabled = False
                scraper_progress.visible = False
                montar_resumo()
                carregar_produtos()
                page.update()

    # ---- COMPARAR PRODUTO COMUM ----

    def _montar_resultado_comparar(resultado):
        comparar_resultados.controls.clear()
        precos = resultado.get("precos", {})
        if not precos:
            comparar_resultados.controls.append(
                ft.Text("Nenhum preco encontrado.", size=12, color=COLORS["text_dim"])
            )
            page.update()
            return

        entries = []
        for sm_id, dados in precos.items():
            sm_info = supermercado_map.get(sm_id)
            nome_sm = sm_info["nome"] if sm_info else sm_id
            entries.append({
                "sm": nome_sm,
                "preco": dados["preco"],
                "nome_prod": dados.get("nome", ""),
            })

        entries.sort(key=lambda x: x["preco"])
        melhor_preco = entries[0]["preco"] if entries else 0

        for entry in entries:
            is_best = entry["preco"] == melhor_preco
            comparar_resultados.controls.append(
                ft.Row([
                    ft.Text(entry["sm"], size=12, width=110, color=COLORS["gold"] if is_best else COLORS["text_dim"]),
                    ft.Text(f"{entry['preco']:.2f}€", size=13, weight="bold", color=COLORS["gold"] if is_best else COLORS["white"]),
                    ft.Text(entry["nome_prod"][:40], size=10, color=COLORS["text_dim"]),
                ], spacing=8)
            )

        if len(entries) > 1:
            poupanca = round(entries[-1]["preco"] - entries[0]["preco"], 2)
            if poupanca > 0:
                comparar_resultados.controls.append(
                    ft.Text(f"Poupanca maxima: {poupanca}€ ({entries[0]['sm']} vs {entries[-1]['sm']})",
                            size=11, color=COLORS["green"])
                )
        page.update()

    def raspar_produto_comparar(e):
        if scraping_lock.locked():
            page.snack_bar = ft.SnackBar(ft.Text("Raspagem ja em curso."), bgcolor=COLORS["text_dim"])
            page.snack_bar.open = True
            page.update()
            return

        query = comparar_field.value.strip()
        if not query:
            page.snack_bar = ft.SnackBar(ft.Text("Escreve o nome do produto."), bgcolor=COLORS["text_dim"])
            page.snack_bar.open = True
            page.update()
            return

        page.run_task(_raspar_produto_comparar_async, query)

    async def _raspar_produto_comparar_async(query):
        nonlocal scraping_lock
        async with scraping_lock:
            btn_comparar.disabled = True
            btn_cabaz.disabled = True
            btn_raspar_todos.disabled = True
            comparar_resultados.controls.clear()
            _init_progress(f"A pesquisar '{query}'...")
            page.update()

            try:
                def cb_progress(sm, produto, termo, progresso):
                    if sm:
                        _update_sm_progress(sm, "Pesquisando...", icon=ft.Icons.SYNC, cor=COLORS["blue"])
                        page.update()

                resultado = await scraper.raspar_produto_comum_async(query, callback=cb_progress)

                precos = resultado.get("precos", {})

                for sm in SUPERMERCADOS:
                    if sm["id"] in precos:
                        dados = precos[sm["id"]]
                        preco = dados["preco"]
                        _update_sm_progress(sm["nome"], f"OK: {dados.get('nome', query)[:25]}", preco=preco, icon=ft.Icons.CHECK_CIRCLE, cor=COLORS["green"])
                    else:
                        _update_sm_progress(sm["nome"], "Nao encontrado", icon=ft.Icons.ERROR, cor=COLORS["red"])

                progress_header.value = f"'{query}' — {len(precos)} supermercados encontrados."
                page.update()

                pid, count = db.salvar_precos_produto_comum(query, resultado)
                _montar_resultado_comparar(resultado)

                if pid:
                    novo_produto = db.listar_produtos(pesquisa=query)
                    if novo_produto:
                        novo_produto = [p for p in novo_produto if p["nome"].lower() == query.lower()]
                        if novo_produto:
                            selecionar_produto(novo_produto[0])

                page.snack_bar = ft.SnackBar(
                    ft.Text(f"{count} precos guardados para '{query}'."),
                    bgcolor=COLORS["green"],
                )
                page.snack_bar.open = True
            except Exception as ex:
                progress_header.value = f"Erro: {ex}"
                page.snack_bar = ft.SnackBar(ft.Text(f"Erro: {ex}"), bgcolor=COLORS["red"])
                page.snack_bar.open = True
            finally:
                btn_comparar.disabled = False
                btn_cabaz.disabled = False
                btn_raspar_todos.disabled = False
                montar_resumo()
                carregar_produtos()
                page.update()

    # ---- UI do Comparar Produto (aqui porque referencia a funcao acima) ----
    comparar_field = ft.TextField(
        hint_text="Ex: leite magro",
        label="Produto",
        border_radius=8,
        bgcolor=COLORS["card_bg"],
        border_color=COLORS["card_border"],
        text_size=13,
        content_padding=ft.padding.Padding(12, 8, 12, 8),
        dense=True,
        width=200,
        on_submit=lambda e: raspar_produto_comparar(e),
    )
    btn_comparar = ft.Button(
        content=ft.Text("Comparar Preco"),
        icon=ft.Icons.COMPARE_ARROWS,
        on_click=raspar_produto_comparar,
        style=ft.ButtonStyle(bgcolor=COLORS["green"], color=COLORS["white"], shape=ft.RoundedRectangleBorder(radius=8)),
    )
    comparar_resultados = ft.Column(spacing=4)

    # ---- Layout ----
    header = ft.Row(
        [
            ft.Column([
                ft.Text("Comparador de Precos", size=28, weight="bold", color=COLORS["white"]),
                ft.Text("Supermercados — Continente, Pingo Doce, Auchan", size=13, color=COLORS["text_dim"]),
            ], spacing=2, expand=True),
            ft.IconButton(icon=ft.Icons.DOWNLOAD, tooltip="Importar da Lista de Compras", icon_color=COLORS["text_dim"], on_click=importar_lista),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    resumo_card = ft.Container(
        content=ft.Column([ft.Text("Resumo", size=14, weight="bold", color=COLORS["white"]), resumo_container], spacing=8),
        bgcolor=COLORS["card_bg"],
        border_radius=12,
        padding=16,
        border=_border(COLORS["card_border"]),
    )

    btn_cabaz = ft.Button(
        content=ft.Text("Raspar Cabaz Basico"),
        icon=ft.Icons.SHOPPING_CART,
        on_click=raspar_cabaz,
        style=ft.ButtonStyle(bgcolor=COLORS["orange"], color=COLORS["white"], shape=ft.RoundedRectangleBorder(radius=8)),
    )
    btn_raspar_todos = ft.Button(
        content=ft.Text("Raspar Todos"),
        icon=ft.Icons.REFRESH,
        on_click=raspar_todos_produtos,
        style=ft.ButtonStyle(bgcolor=COLORS["blue"], color=COLORS["white"], shape=ft.RoundedRectangleBorder(radius=8)),
    )

    scraper_row = ft.Row(
        [
            btn_cabaz,
            btn_raspar_todos,
            scraper_progress,
        ],
        spacing=12,
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    scraper_card = ft.Container(
        content=ft.Column([
            ft.Text("Raspagem de Precos Online", size=14, weight="bold", color=COLORS["white"]),
            ft.Text("Pesquisa automatica nos sites dos supermercados. O cabaz basico tem 28 produtos essenciais.", size=12, color=COLORS["text_dim"]),
            ft.Divider(height=1, color=COLORS["card_border"]),
            ft.Text("Cabaz Basico", size=12, weight="bold", color=COLORS["text_dim"]),
            scraper_row,
            ft.Divider(height=1, color=COLORS["card_border"]),
            ft.Text("Comparar Produto Comum", size=12, weight="bold", color=COLORS["text_dim"]),
            ft.Row([
                comparar_field,
                btn_comparar,
            ], spacing=10),
            progress_container,
            ft.Container(
                content=comparar_resultados,
                bgcolor=COLORS["bg"],
                border_radius=8,
                padding=10,
                visible=True,
            ),
        ], spacing=8),
        bgcolor=COLORS["card_bg"],
        border_radius=12,
        padding=16,
        border=_border(COLORS["card_border"]),
    )

    cat_dropdown = ft.Dropdown(
        options=[ft.dropdown.Option("Todas")] + [ft.dropdown.Option(c) for c in CATEGORIAS],
        value="Todas",
        on_select=filtrar_categoria,
        border_radius=8,
        bgcolor=COLORS["card_bg"],
        border_color=COLORS["card_border"],
        text_size=12,
        width=180,
        content_padding=ft.padding.Padding(12, 8, 12, 8),
        dense=True,
    )

    search_field = ft.TextField(
        hint_text="Pesquisar...",
        prefix_icon=ft.Icons.SEARCH,
        border_radius=8,
        bgcolor=COLORS["card_bg"],
        border_color=COLORS["card_border"],
        text_size=13,
        content_padding=ft.padding.Padding(12, 8, 12, 8),
        dense=True,
        on_submit=lambda e: carregar_produtos(e.control.value if e.control.value.strip() else None),
    )

    botoes_row = ft.Row(
        [
            ft.Button(content=ft.Text("+ Adicionar"), icon=ft.Icons.ADD, on_click=adicionar_produto_dialog,
                style=ft.ButtonStyle(bgcolor=COLORS["blue"], color=COLORS["white"], shape=ft.RoundedRectangleBorder(radius=8))),
            ft.IconButton(icon=ft.Icons.DELETE, tooltip="Apagar selecionado", icon_color=COLORS["red"], on_click=apagar_produto),
        ],
    )

    top_bar = ft.Row([cat_dropdown, search_field, botoes_row], spacing=12, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    left_panel = ft.Container(
        content=ft.Column([top_bar, ft.Divider(height=1, color=COLORS["card_border"]), produto_lista], spacing=10, expand=True),
        bgcolor=COLORS["card_bg"],
        border_radius=12,
        padding=16,
        border=_border(COLORS["card_border"]),
        expand=2,
    )

    right_panel = ft.Container(
        content=ft.Column([preco_inputs_container], spacing=10, scroll=ft.ScrollMode.AUTO, expand=True),
        bgcolor=COLORS["card_bg"],
        border_radius=12,
        padding=16,
        border=_border(COLORS["card_border"]),
        expand=1,
    )

    page.add(
        ft.Column([
            header,
            ft.Divider(height=1, color=COLORS["card_border"]),
            resumo_card,
            scraper_card,
            ft.Row([left_panel, right_panel], spacing=16, expand=True),
        ], spacing=16, expand=True, scroll=ft.ScrollMode.AUTO)
    )

    montar_resumo()
    carregar_produtos()


if __name__ == "__main__":
    ft.run(main)
