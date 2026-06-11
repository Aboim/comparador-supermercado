# Comparador de Precos de Supermercado

COLORS = {
    "bg": "#0F172A",
    "card_bg": "#1E293B",
    "card_border": "#334155",
    "gold": "#FFD700",
    "blue": "#2E5BFF",
    "orange": "#FB923C",
    "green": "#22C55E",
    "red": "#EF4444",
    "text": "#E2E8F0",
    "text_dim": "#94A3B8",
    "white": "#F8FAFC",
}

SUPERMERCADOS = [
    {"id": "continente", "nome": "Continente", "cor": "#EF4444", "icone": "\U0001f6d2",
     "url": "https://www.continente.pt/pesquisa/?q={query}",
     "needs_js": True},
    {"id": "pingo_doce", "nome": "Pingo Doce", "cor": "#EF4444", "icone": "\U0001f6d2",
     "url": "https://www.pingodoce.pt/pesquisa/?q={query}",
     "needs_js": True},
    {"id": "auchan", "nome": "Auchan", "cor": "#EF4444", "icone": "\U0001f6d2",
     "url": "https://www.auchan.pt/pt/pesquisa?q={query}",
     "needs_js": False},
    {"id": "minipreco", "nome": "Minipreco", "cor": "#3B82F6", "icone": "\U0001f3ea",
     "url": "https://www.auchan.pt/pt/pesquisa?q={query}",
     "needs_js": False},
]

CATEGORIAS = [
    "Frutas e Legumes",
    "Laticinios",
    "Carne e Peixe",
    "Mercearia",
    "Bebidas",
    "Congelados",
    "Padaria",
    "Higiene",
    "Limpeza",
    "Outros",
]

CABAZ_BASICO = [
    {"nome": "Leite Meio-Gordo 1L", "categoria": "Laticinios", "unidade": "un",
     "termos_pesquisa": ["leite meio gordo 1l", "leite uht meio gordo", "leite meio-gordo"]},
    {"nome": "Leite Magro 1L", "categoria": "Laticinios", "unidade": "un",
     "termos_pesquisa": ["leite magro 1l", "leite uht magro", "leite magro"]},
    {"nome": "Pao de Forma 500g", "categoria": "Padaria", "unidade": "un",
     "termos_pesquisa": ["pao de forma 500g", "pao de forma fatiado", "pao forma"]},
    {"nome": "Ovos M 6 un", "categoria": "Laticinios", "unidade": "un",
     "termos_pesquisa": ["ovos m 6", "ovos classe m", "ovos 6 unidades"]},
    {"nome": "Arroz Agulha 1kg", "categoria": "Mercearia", "unidade": "un",
     "termos_pesquisa": ["arroz agulha 1kg", "arroz agulha", "arroz 1kg"]},
    {"nome": "Massa Esparguete 500g", "categoria": "Mercearia", "unidade": "un",
     "termos_pesquisa": ["massa esparguete 500g", "esparguete 500g", "massa esparguete"]},
    {"nome": "Acucar Branco 1kg", "categoria": "Mercearia", "unidade": "un",
     "termos_pesquisa": ["acucar branco 1kg", "acucar 1kg", "acucar branco"]},
    {"nome": "Farinha de Trigo 1kg", "categoria": "Mercearia", "unidade": "un",
     "termos_pesquisa": ["farinha trigo 1kg", "farinha de trigo", "farinha 1kg"]},
    {"nome": "Oleo Alimentar 1L", "categoria": "Mercearia", "unidade": "un",
     "termos_pesquisa": ["oleo alimentar 1l", "oleo girassol 1l", "oleo 1l"]},
    {"nome": "Azeite Virgem Extra 75cl", "categoria": "Mercearia", "unidade": "un",
     "termos_pesquisa": ["azeite virgem extra 75cl", "azeite virgem extra", "azeite 75cl"]},
    {"nome": "Peito de Frango 1kg", "categoria": "Carne e Peixe", "unidade": "kg",
     "termos_pesquisa": ["peito de frango", "peito frango kg", "frango peito"]},
    {"nome": "Costeletas de Porco 1kg", "categoria": "Carne e Peixe", "unidade": "kg",
     "termos_pesquisa": ["costeletas porco", "costeleta porco kg", "entremeada porco"]},
    {"nome": "Pescada Filetes 400g", "categoria": "Carne e Peixe", "unidade": "un",
     "termos_pesquisa": ["filetes pescada 400g", "pescada filetes", "filetes de pescada"]},
    {"nome": "Atum Posta 120g", "categoria": "Mercearia", "unidade": "un",
     "termos_pesquisa": ["atum posta 120g", "atum em agua", "atum lata"]},
    {"nome": "Feijao Vermelho 500g", "categoria": "Mercearia", "unidade": "un",
     "termos_pesquisa": ["feijao vermelho 500g", "feijao encarnado", "feijao lata"]},
    {"nome": "Batatas 1kg", "categoria": "Frutas e Legumes", "unidade": "kg",
     "termos_pesquisa": ["batata 1kg", "batata para cozer", "batatas kg"]},
    {"nome": "Cebolas 1kg", "categoria": "Frutas e Legumes", "unidade": "kg",
     "termos_pesquisa": ["cebola 1kg", "cebola kg", "cebolas"]},
    {"nome": "Alho 200g", "categoria": "Frutas e Legumes", "unidade": "un",
     "termos_pesquisa": ["alho 200g", "alho", "dentes de alho"]},
    {"nome": "Tomate 1kg", "categoria": "Frutas e Legumes", "unidade": "kg",
     "termos_pesquisa": ["tomate 1kg", "tomate coracao de boi", "tomate kg"]},
    {"nome": "Macas 1kg", "categoria": "Frutas e Legumes", "unidade": "kg",
     "termos_pesquisa": ["maca golden 1kg", "maca kg", "macas golden"]},
    {"nome": "Banana 1kg", "categoria": "Frutas e Legumes", "unidade": "kg",
     "termos_pesquisa": ["banana kg", "banana 1kg", "banana madeira"]},
    {"nome": "Agua Mineral 6x1.5L", "categoria": "Bebidas", "unidade": "un",
     "termos_pesquisa": ["agua mineral 6x1.5l", "agua 1.5l pack", "agua mineral pack"]},
    {"nome": "Cerveja 33cl", "categoria": "Bebidas", "unidade": "un",
     "termos_pesquisa": ["cerveja 33cl", "cerveja lata", "cerveja pack"]},
    {"nome": "Cafe Moagem Normal 250g", "categoria": "Mercearia", "unidade": "un",
     "termos_pesquisa": ["cafe 250g", "cafe moagem normal", "cafe moido 250g"]},
    {"nome": "Papel Higienico 6 Rolos", "categoria": "Higiene", "unidade": "un",
     "termos_pesquisa": ["papel higienico 6 rolos", "papel higienico pack", "rolo papel"]},
    {"nome": "Detergente Roupa 1.5L", "categoria": "Limpeza", "unidade": "un",
     "termos_pesquisa": ["detergente roupa liquido 1.5l", "detergente roupa 1.5l", "detergente maquina roupa"]},
    {"nome": "Lixivia 1L", "categoria": "Limpeza", "unidade": "un",
     "termos_pesquisa": ["lixivia 1l", "lixivia roupa", "lixivia"]},
    {"nome": "Amaciador Roupa 1L", "categoria": "Limpeza", "unidade": "un",
     "termos_pesquisa": ["amaciador roupa 1l", "amaciador 1l", "amaciador roupa"]},
]

SCRAPER_TIMEOUT = 15
SCRAPER_MAX_RESULTS = 3
SCRAPER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

SCRAPER_SELECTORS = {
    "continente": {
        "item": ".product-tile, [class*='product'][class*='tile'], [class*='ProductTile']",
        "name": ".product-tile__title, [class*='product'][class*='title'], h2, h3, [class*='name']",
        "price": ".price-value, [class*='price'], [class*='Price'] span, [class*='value']",
        "unit": ".product-tile__unit, [class*='unit'], [class*='quantity']",
    },
    "pingo_doce": {
        "item": "article.product-item, [class*='product'][class*='item'], li[class*='product']",
        "name": ".product-item__name, [class*='product'][class*='name'], h3, [class*='title']",
        "price": ".price-value, [class*='price'] span, [class*='Price-value']",
        "unit": ".product-item__unit, [class*='unit'], [class*='quantity']",
    },
    "auchan": {
        "item": ".product-card, [class*='product'][class*='card'], .product-thumbnail",
        "name": ".product-card__title, [class*='product'][class*='title'], [class*='name'], h3",
        "price": ".product-price__value, [class*='price'] [class*='value'], [class*='Price-value']",
        "unit": ".product-price__unit, [class*='unit'], [class*='quantity']",
    },
    "minipreco": {
        "item": ".product-card, [class*='product'][class*='card'], .product-thumbnail",
        "name": ".product-card__title, [class*='product'][class*='title'], [class*='name'], h3",
        "price": ".product-price__value, [class*='price'] [class*='value'], [class*='Price-value']",
        "unit": ".product-price__unit, [class*='unit'], [class*='quantity']",
    },
}

SCRAPER_GENERIC_PRICE_PATTERNS = [
    r'(\d+[.,]\d{2})\s*€',
    r'€\s*(\d+[.,]\d{2})',
    r'(\d+[.,]\d{2})\s*EUR',
    r'(\d+[.,]\d{2})/?\s*(?:un|kg|l|lt|g|ml)',
]

SCRAPER_JSONLD_KEYWORDS = ["Product", "product", "price", "offers", "Offer"]

SCRAPER_CATEGORIES = {
    "Laticinios": ["leite", "ovos", "queijo", "iogurte", "manteiga", "natas"],
    "Padaria": ["pao", "bolo", "broa", "tosta"],
    "Mercearia": ["arroz", "massa", "acucar", "oleo", "azeite", "cafe", "farinha", "sal", "enlatado", "atum", "feijao", "grao"],
    "Carne e Peixe": ["frango", "porco", "vaca", "peixe", "bacalhau", "costeleta", "bife", "carne"],
    "Frutas e Legumes": ["batata", "cebola", "alho", "tomate", "maca", "banana", "laranja", "pera", "alface", "cenoura", "couve"],
    "Bebidas": ["agua", "sumo", "refrigerante", "cerveja", "vinho"],
    "Higiene": ["papel higienico", "pasta dentes", "sabonete", "shampoo", "gel banho", "desodorizante"],
    "Limpeza": ["detergente", "lixivia", "amaciador", "esfregoes", "saco lixo"],
    "Congelados": ["congelado", "pescada", "douradinhos", "legumes congelados", "gelado"],
    "Outros": [],
}
