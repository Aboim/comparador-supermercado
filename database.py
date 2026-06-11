import sqlite3
import os
from config import SUPERMERCADOS, CATEGORIAS, CABAZ_BASICO

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "precos.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            categoria TEXT NOT NULL DEFAULT 'Mercearia',
            unidade TEXT DEFAULT 'un',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS precos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            supermercado_id TEXT NOT NULL,
            preco REAL NOT NULL,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE CASCADE,
            UNIQUE(produto_id, supermercado_id)
        );
    """)
    db.commit()
    db.close()


def listar_produtos(categoria=None, pesquisa=None):
    db = get_db()
    query = "SELECT * FROM produtos WHERE 1=1"
    params = []
    if categoria and categoria != "Todas":
        query += " AND categoria = ?"
        params.append(categoria)
    if pesquisa:
        query += " AND nome LIKE ?"
        params.append(f"%{pesquisa}%")
    query += " ORDER BY categoria, nome"
    rows = db.execute(query, params).fetchall()
    db.close()
    return [dict(r) for r in rows]


def adicionar_produto(nome, categoria, unidade="un"):
    db = get_db()
    cursor = db.execute(
        "INSERT INTO produtos (nome, categoria, unidade) VALUES (?, ?, ?)",
        (nome.strip(), categoria, unidade),
    )
    db.commit()
    pid = cursor.lastrowid
    db.close()
    return pid


def atualizar_produto(pid, nome, categoria, unidade):
    db = get_db()
    db.execute(
        "UPDATE produtos SET nome=?, categoria=?, unidade=? WHERE id=?",
        (nome.strip(), categoria, unidade, pid),
    )
    db.commit()
    db.close()


def remover_produto(pid):
    db = get_db()
    db.execute("DELETE FROM produtos WHERE id=?", (pid,))
    db.commit()
    db.close()


def listar_precos(produto_id=None):
    db = get_db()
    if produto_id:
        rows = db.execute(
            "SELECT * FROM precos WHERE produto_id=? ORDER BY supermercado_id",
            (produto_id,),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM precos ORDER BY produto_id, supermercado_id").fetchall()
    db.close()
    return [dict(r) for r in rows]


def atualizar_preco(produto_id, supermercado_id, preco):
    db = get_db()
    db.execute(
        """INSERT INTO precos (produto_id, supermercado_id, preco, atualizado_em)
           VALUES (?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(produto_id, supermercado_id)
           DO UPDATE SET preco=?, atualizado_em=CURRENT_TIMESTAMP""",
        (produto_id, supermercado_id, preco, preco),
    )
    db.commit()
    db.close()


def remover_preco(produto_id, supermercado_id):
    db = get_db()
    db.execute(
        "DELETE FROM precos WHERE produto_id=? AND supermercado_id=?",
        (produto_id, supermercado_id),
    )
    db.commit()
    db.close()


def obter_comparativo():
    """Retorna o custo total por supermercado para todos os produtos com precos."""
    db = get_db()
    rows = db.execute("""
        SELECT s.supermercado_id,
               COUNT(DISTINCT s.produto_id) as itens,
               ROUND(SUM(s.preco), 2) as total
        FROM precos s
        GROUP BY s.supermercado_id
        ORDER BY total ASC
    """).fetchall()
    db.close()
    return [dict(r) for r in rows]


def obter_precos_por_produto(produto_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM precos WHERE produto_id=? ORDER BY preco ASC",
        (produto_id,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def importar_lista_compras():
    """Tenta importar produtos da Lista de Compras via SQLite."""
    base = os.path.dirname(os.path.abspath(__file__))
    lista_db = os.path.join(base, "..", "Lista de Compras", "shopping_list.db")
    if not os.path.exists(lista_db):
        return 0

    try:
        ldb = sqlite3.connect(lista_db)
        ldb.row_factory = sqlite3.Row
        items = ldb.execute(
            "SELECT name, category FROM items WHERE category IS NOT NULL"
        ).fetchall()
        ldb.close()

        db = get_db()
        count = 0
        for item in items:
            existing = db.execute(
                "SELECT id FROM produtos WHERE nome=?", (item["name"].strip(),)
            ).fetchone()
            if not existing:
                db.execute(
                    "INSERT INTO produtos (nome, categoria, unidade) VALUES (?, ?, 'un')",
                    (item["name"].strip(), item["category"] or "Mercearia"),
                )
                count += 1
        db.commit()
        db.close()
        return count
    except Exception:
        return -1


def adicionar_cabaz_basico():
    """Insere os produtos do cabaz basico se ainda nao existirem."""
    db = get_db()
    count = 0
    for produto in CABAZ_BASICO:
        existing = db.execute("SELECT id FROM produtos WHERE nome=?", (produto["nome"],)).fetchone()
        if not existing:
            db.execute(
                "INSERT INTO produtos (nome, categoria, unidade) VALUES (?, ?, ?)",
                (produto["nome"], produto["categoria"], produto["unidade"]),
            )
            count += 1
    db.commit()
    db.close()
    return count


def atualizar_precos_em_massa(resultados_cabaz):
    """Guarda precos raspados do cabaz basico.
    resultados_cabaz: [{"nome": str, "categoria": str, "unidade": str,
                        "precos": {sm_id: {"preco": float, "nome": str}}}]
    """
    if not resultados_cabaz:
        return 0

    db = get_db()
    count = 0

    for item in resultados_cabaz:
        row = db.execute("SELECT id FROM produtos WHERE nome=?", (item["nome"],)).fetchone()
        if not row:
            cursor = db.execute(
                "INSERT INTO produtos (nome, categoria, unidade) VALUES (?, ?, ?)",
                (item["nome"], item["categoria"], item["unidade"]),
            )
            pid = cursor.lastrowid
        else:
            pid = row["id"]

        for sm_id, dados in item["precos"].items():
            db.execute(
                """INSERT INTO precos (produto_id, supermercado_id, preco, atualizado_em)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(produto_id, supermercado_id)
                   DO UPDATE SET preco=?, atualizado_em=CURRENT_TIMESTAMP""",
                (pid, sm_id, dados["preco"], dados["preco"]),
            )
            count += 1

    db.commit()
    db.close()
    return count


def atualizar_precos_por_scraper(precos_dict):
    """Guarda precos raspados para produtos existentes.
    precos_dict: {produto_id: {sm_id: preco}}
    """
    if not precos_dict:
        return 0

    db = get_db()
    count = 0
    for pid, sm_precos in precos_dict.items():
        for sm_id, preco in sm_precos.items():
            db.execute(
                """INSERT INTO precos (produto_id, supermercado_id, preco, atualizado_em)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(produto_id, supermercado_id)
                   DO UPDATE SET preco=?, atualizado_em=CURRENT_TIMESTAMP""",
                (pid, sm_id, preco, preco),
            )
            count += 1
    db.commit()
    db.close()
    return count


def salvar_precos_produto_comum(nome_produto, resultados):
    """Guarda os precos de um produto comum raspado em todos os supermercados.
    resultados: {"query": str, "precos": {sm_id: {"preco": float, "nome": str, "unidade": str}}}
    Retorna o product_id e o numero de precos guardados."""
    if not resultados or not resultados.get("precos"):
        return None, 0

    db = get_db()

    row = db.execute("SELECT id FROM produtos WHERE nome=?", (nome_produto,)).fetchone()
    if row:
        pid = row["id"]
    else:
        cursor = db.execute(
            "INSERT INTO produtos (nome, categoria, unidade) VALUES (?, ?, ?)",
            (nome_produto, "Mercearia", "un"),
        )
        pid = cursor.lastrowid

    count = 0
    for sm_id, dados in resultados["precos"].items():
        db.execute(
            """INSERT INTO precos (produto_id, supermercado_id, preco, atualizado_em)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(produto_id, supermercado_id)
               DO UPDATE SET preco=?, atualizado_em=CURRENT_TIMESTAMP""",
            (pid, sm_id, dados["preco"], dados["preco"]),
        )
        count += 1

    db.commit()
    db.close()
    return pid, count


def obter_comparativo_produto(produto_id):
    """Retorna precos de um produto em todos os supermercados, ordenado por preco."""
    db = get_db()
    rows = db.execute(
        "SELECT supermercado_id, preco, atualizado_em FROM precos WHERE produto_id=? ORDER BY preco ASC",
        (produto_id,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]
