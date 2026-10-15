#!/usr/bin/env python3
"""
Scraper de Coto Digital -> PostgreSQL/Supabase (esquema de schema.sql).

Estrategia (el sitio nuevo de Coto es una SPA que consulta un backend JSON):
  1) Abre la categoría con Playwright y captura las respuestas XHR/fetch en JSON.
  2) Extrae productos de forma tolerante (busca listas de dicts "con pinta de producto").
  3) Si no capturó nada, cae a leer las tarjetas del DOM (sin EAN).
  4) Limpia texto, convierte precios a float, y hace upsert en la base.

Uso:
  pip install playwright "psycopg[binary]"
  playwright install chromium

  # Probar sin tocar la base, guardando los JSON crudos para inspeccionarlos:
  python coto_scraper.py --dry-run --max-pages 1 --debug-dir debug/

  # Corrida real:
  export DATABASE_URL="postgresql://postgres:...@db.xxx.supabase.co:5432/postgres"
  python coto_scraper.py --max-pages 20
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlparse, urlunparse

BASE = "https://www.cotodigital.com.ar"
RETAILER_SLUG = "coto"
STORE_EXTERNAL_ID = "200"   # contexto de sucursal por defecto de Coto Digital (precios online)

# Agregá acá las categorías que quieras (copiá la URL desde el navegador).
# Ejemplo verificado en fuentes públicas: Bebidas sin alcohol > Aguas.
DEFAULT_CATEGORIES = [
    f"{BASE}/sitios/cdigi/productos/categorias/catalogo-bebidas-bebidas-sin-alcohol-aguas/catv00004086",
]


# ======================================================================
# Cortesía y anti-bloqueo
# ======================================================================
BLOCK_STATUS = {403, 429, 503}
BLOCK_TITLES = ("just a moment", "attention required", "access denied", "acceso denegado",
                "captcha", "pardon our interruption")


class BlockedError(Exception):
    """El sitio nos limita o bloquea: hay que frenar, no insistir."""


def make_user_agent(chromium_version: str) -> str:
    """UA coherente con el Chromium real que corre (evita el 'HeadlessChrome' por defecto y
    versiones viejas hardcodeadas). Se elige UNO por corrida: cambiar de UA entre pedidos
    de una misma sesión es más sospechoso que mantenerlo."""
    major = chromium_version.split(".")[0]
    platform = random.choice(["Windows NT 10.0; Win64; x64", "Macintosh; Intel Mac OS X 10_15_7",
                            "X11; Linux x86_64"])
    return f"Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36"


def proxy_from_env() -> dict | None:
    """PROXY_URL=http://usuario:clave@host:puerto (opcional)."""
    raw = os.environ.get("PROXY_URL")
    if not raw:
        return None
    u = urlparse(raw)
    cfg = {"server": f"{u.scheme}://{u.hostname}:{u.port}"}
    if u.username:
        cfg["username"], cfg["password"] = unquote(u.username), unquote(u.password or "")
    return cfg


def goto_with_retry(page, url: str, retries: int = 3) -> None:
    """Navega con backoff exponencial + jitter. Respeta Retry-After en 429.
    Si tras los reintentos sigue bloqueado, levanta BlockedError (el llamador corta la corrida)."""
    for attempt in range(1, retries + 1):
        resp, error = None, None
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:                        # timeout, DNS, conexión cortada
            error = e
        status = resp.status if resp else None
        title = ""
        if resp:
            try:
                title = (page.title() or "").lower()
            except Exception:
                pass
        blocked = status in BLOCK_STATUS or any(t in title for t in BLOCK_TITLES)
        if resp and not blocked and (status < 400 or status == 404):    # 404 = página fuera de rango
            return
        if attempt == retries:
            raise BlockedError(f"{url} -> status={status} title={title!r} error={error}")
        wait = min(300, 20 * 2 ** (attempt - 1)) + random.uniform(0, 10)
        if status == 429 and resp:
            try:
                wait = max(wait, float(resp.headers.get("retry-after", 0)))
            except ValueError:
                pass
        print(f"     intento {attempt}/{retries} falló (status={status}); espero {wait:.0f}s")
        time.sleep(wait)


# ======================================================================
# Limpieza y parseo
# ======================================================================
def clean_text(s: str | None) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s or "")).strip()


def normalize_text(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9.,% ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_price(v) -> float | None:
    """'$ 1.234,56' -> 1234.56 ; 1234.5 -> 1234.5 ; '' -> None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2) if v > 0 else None
    m = re.search(r"\d[\d.,]*", str(v))
    if not m:
        return None
    num = m.group(0).rstrip(".,")
    if "," in num and "." in num:
        if num.rfind(",") > num.rfind("."):        # 1.234,56
            num = num.replace(".", "").replace(",", ".")
        else:                                       # 1,234.56
            num = num.replace(",", "")
    elif "," in num:                                # 12,50
        num = num.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", num):   # 1.234 (miles)
        num = num.replace(".", "")
    try:
        val = float(num)
    except ValueError:
        return None
    return round(val, 2) if val > 0 else None


def normalize_ean(raw) -> str | None:
    """GTIN válido (dígito verificador) o None."""
    if not raw:
        return None
    d = re.sub(r"\D", "", str(raw))
    if len(d) == 14 and d[0] == "0":
        d = d[1:]
    if len(d) == 12:
        d = "0" + d
    if len(d) not in (8, 13):
        return None
    body, check = d[:-1], int(d[-1])
    total = sum(int(x) * (3 if i % 2 == 0 else 1) for i, x in enumerate(reversed(body)))
    return d if (10 - total % 10) % 10 == check else None


UNIT_TO_BASE = {"kg": ("g", 1000), "g": ("g", 1), "gr": ("g", 1), "grs": ("g", 1),
                "l": ("ml", 1000), "lt": ("ml", 1000), "lts": ("ml", 1000),
                "ml": ("ml", 1), "cc": ("ml", 1), "un": ("un", 1), "u": ("un", 1), "unid": ("un", 1)}
SIZE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|grs?|g|lts?|l|ml|cc|unid|un|u)\b")
PACK_RE = re.compile(r"\b(?:pack\s*)?x\s*(\d+)\b(?!\s*(?:kg|grs?|g|lts?|l|ml|cc)\b)")


def parse_size(name: str) -> tuple[float | None, str | None, int, str | None]:
    """-> (size_base, size_unit, pack_qty, texto_medida)."""
    n = normalize_text(name)
    size_base = size_unit = text = None
    if m := SIZE_RE.search(n):
        unit, factor = UNIT_TO_BASE[m.group(2)]
        size_base = float(m.group(1).replace(",", ".")) * factor
        size_unit, text = unit, m.group(0)
    pack = int(m.group(1)) if (m := PACK_RE.search(n)) else 1
    return size_base, size_unit, pack, text


# ======================================================================
# Modelo + extracción desde JSON
# ======================================================================
@dataclass
class Product:
    external_id: str
    name: str
    url: str | None
    regular_price: float | None
    sale_price: float | None
    brand: str | None = None
    ean: str | None = None
    raw_ean: str | None = None
    image_url: str | None = None
    in_stock: bool = True
    category: str | None = None
    unit_text: str | None = None
    size_base: float | None = None
    size_unit: str | None = None
    pack_qty: int = 1


NAME_KEYS = ["value", "name", "title", "product_name", "displayname", "product.displayname", "description"]
REG_KEYS = ["regular_price", "list_price", "listprice", "precio_regular", "precio_lista", "preciolista", "price_regular"]
SALE_KEYS = ["sale_price", "discount_price", "price_discount", "precio_oferta", "precio_descuento", "offer_price", "precio_final"]
PRICE_KEYS = ["price", "activeprice", "sku.activeprice", "precio"]
EAN_KEYS = ["ean", "gtin", "gtin13", "ean13", "barcode", "codigo_barras", "product.ean"]
BRAND_KEYS = ["brand", "marca", "product.brand", "manufacturer"]
ID_KEYS = ["id", "sku", "sku_id", "repositoryid", "sku.repositoryid", "product.repositoryid"]
URL_KEYS = ["url", "link", "product_url", "producturl"]
IMG_KEYS = ["image_url", "imageurl", "image", "img", "thumbnail"]
STOCK_KEYS = ["in_stock", "instock", "available", "disponible"]


def _flat(d: dict) -> dict:
    flat = {str(k).lower(): v for k, v in d.items()}
    if isinstance(d.get("data"), dict):            # formato tipo Constructor.io: {value, data:{...}}
        for k, v in d["data"].items():
            flat.setdefault(str(k).lower(), v)
    return flat


def _pick(flat: dict, keys: list[str]):
    for k in keys:
        v = flat.get(k)
        if v not in (None, "", [], {}):
            return v
    return None


def id_from_url(url: str | None) -> str | None:
    m = re.search(r"/R-(\d+)-", url or "")
    return m.group(1) if m else None


def category_from_url(url: str) -> str | None:
    m = re.search(r"/categorias/([^/?]+)", url)
    return m.group(1) if m else None


def product_from_dict(d: dict, category: str | None) -> Product | None:
    flat = _flat(d)
    name = clean_text(str(_pick(flat, NAME_KEYS) or ""))
    raw_url = _pick(flat, URL_KEYS)
    url = urljoin(BASE, raw_url) if isinstance(raw_url, str) else None
    ext_id = id_from_url(url) or (str(_pick(flat, ID_KEYS)) if _pick(flat, ID_KEYS) is not None else None)

    regular = parse_price(_pick(flat, REG_KEYS))
    sale = parse_price(_pick(flat, SALE_KEYS))
    base = parse_price(_pick(flat, PRICE_KEYS))
    if regular is None:
        regular = base
    elif sale is None and base is not None and base < regular:
        sale = base
    if regular is None and sale is not None:
        regular, sale = sale, None
    if sale is not None and regular is not None and sale >= regular:
        sale = None

    if not (name and ext_id and regular):
        return None

    raw_ean = _pick(flat, EAN_KEYS)
    size_base, size_unit, pack, unit_text = parse_size(name)
    stock = _pick(flat, STOCK_KEYS)
    img = _pick(flat, IMG_KEYS)
    brand = _pick(flat, BRAND_KEYS)
    return Product(
        external_id=ext_id, name=name, url=url, regular_price=regular, sale_price=sale,
        brand=clean_text(str(brand)) if brand else None,
        ean=normalize_ean(raw_ean), raw_ean=str(raw_ean) if raw_ean else None,
        image_url=img if isinstance(img, str) else None,
        in_stock=bool(stock) if stock is not None else True,
        category=category, unit_text=unit_text, size_base=size_base, size_unit=size_unit, pack_qty=pack,
    )


def extract_from_json(obj, category: str | None) -> list[Product]:
    """Recorre el JSON y toma cada dict que parezca un producto (no recursa dentro de él)."""
    found: list[Product] = []

    def walk(o):
        if isinstance(o, dict):
            p = product_from_dict(o, category)
            if p:
                found.append(p)
                return
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(obj)
    return found


# ======================================================================
# Playwright
# ======================================================================
class Capture:
    """Acumula las respuestas JSON (XHR/fetch) que dispara la página."""

    def __init__(self, debug_dir: Path | None):
        self.items: list[tuple[str, object]] = []
        self.debug_dir = debug_dir
        self._n = 0
        self.blocked = False   # True si el sitio nos frenó durante la corrida

    def on_response(self, response):
        try:
            if response.request.resource_type not in ("xhr", "fetch"):
                return
            if "json" not in (response.headers.get("content-type") or ""):
                return
            data = response.json()
        except Exception:
            return
        self.items.append((response.url, data))
        if self.debug_dir:
            self._n += 1
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            (self.debug_dir / f"{self._n:03d}.json").write_text(
                json.dumps({"url": response.url, "data": data}, ensure_ascii=False, indent=1))

    def clear(self):
        self.items.clear()


def page_url(url: str, n: int) -> str:
    if n <= 1:
        return url
    p = urlparse(url)
    q = dict(parse_qsl(p.query))
    q["page"] = str(n)
    return urlunparse(p._replace(query=urlencode(q)))


def dom_fallback(page, category: str | None) -> list[Product]:
    """Último recurso: lee tarjetas del DOM. No trae EAN y es frágil ante cambios de diseño."""
    cards = page.evaluate("""() => Array.from(document.querySelectorAll('a[href*="/productos/_/"]')).map(a => {
        const card = a.closest('article, li, [class*="card"], [class*="product"]') || a.parentElement;
        return {href: a.href, text: (card || a).innerText};
    })""")
    out, seen = [], set()
    for c in cards:
        ext_id = id_from_url(c["href"])
        if not ext_id or ext_id in seen:
            continue
        lines = [clean_text(x) for x in c["text"].split("\n") if clean_text(x)]
        name = next((x for x in lines if len(x) > 3 and not re.match(r"^[$\d]|%|off|agregar|comprar", x, re.I)), None)
        prices = sorted({p for p in (parse_price(m) for m in re.findall(r"\$\s*[\d.]+(?:,\d{1,2})?", c["text"])) if p})
        if not (name and prices):
            continue
        seen.add(ext_id)
        regular, sale = prices[-1], (prices[0] if len(prices) > 1 else None)
        sb, su, pk, ut = parse_size(name)
        out.append(Product(ext_id, name, c["href"], regular, sale, category=category,
                           unit_text=ut, size_base=sb, size_unit=su, pack_qty=pk))
    return out


def scrape_category(page, cap: Capture, url: str, max_pages: int, delay: tuple[float, float]) -> list[Product]:
    category = category_from_url(url)
    products: dict[str, Product] = {}
    for n in range(1, max_pages + 1):
        cap.clear()
        target = page_url(url, n)
        print(f"  -> página {n}: {target}")
        try:
            goto_with_retry(page, target)
        except BlockedError as e:
            print(f"     BLOQUEO: {e}. Corto la corrida sin insistir; se guarda lo obtenido.")
            cap.blocked = True
            break
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass
        for _ in range(4):                      # scroll para disparar lazy-loading
            page.mouse.wheel(0, 2500)
            page.wait_for_timeout(600)

        batch = [p for _, data in cap.items for p in extract_from_json(data, category)]
        source = "json"
        if not batch:
            batch, source = dom_fallback(page, category), "dom"
        new = [p for p in batch if p.external_id not in products]
        print(f"     {len(batch)} productos ({source}), {len(new)} nuevos")
        if not new:                           # página vacía o repetida = fin
            break
        products.update({p.external_id: p for p in new})
        time.sleep(random.uniform(*delay))
        if random.random() < 0.1:               # pausa larga ocasional: tráfico menos mecánico
            time.sleep(random.uniform(10, 25))
    return list(products.values())


# ======================================================================
# Base de datos
# ======================================================================
def save_products(conn, products: list[Product], status: str = 'ok') -> dict:
    stats = {"listings": 0, "prices_inserted": 0, "prices_unchanged": 0}
    with conn.cursor() as cur:
        cur.execute(
            """insert into retailers (name, slug, website) values ('Coto', %s, %s)
               on conflict (slug) do update set website = excluded.website returning id""",
            (RETAILER_SLUG, BASE))
        retailer_id = cur.fetchone()[0]
        cur.execute(
            """insert into stores (retailer_id, external_id, name, is_online)
               values (%s, %s, 'Coto Digital (online)', true)
               on conflict (retailer_id, external_id) do update set name = excluded.name returning id""",
            (retailer_id, STORE_EXTERNAL_ID))
        store_id = cur.fetchone()[0]
        cur.execute("insert into scrape_runs (retailer_id) values (%s) returning id", (retailer_id,))
        run_id = cur.fetchone()[0]

        for p in products:
            cur.execute(
                """insert into retailer_products
                     (retailer_id, external_id, url, raw_name, raw_brand, raw_category, raw_ean, ean,
                      image_url, normalized_name, parsed_brand, size_base, size_unit, pack_qty,
                      is_active, last_seen_at)
                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true,now())
                    on conflict (retailer_id, external_id) do update set
                      url = excluded.url, raw_name = excluded.raw_name, raw_brand = excluded.raw_brand,
                      raw_category = excluded.raw_category,
                      raw_ean = coalesce(excluded.raw_ean, retailer_products.raw_ean),
                      ean = coalesce(excluded.ean, retailer_products.ean),
                      image_url = excluded.image_url, normalized_name = excluded.normalized_name,
                      parsed_brand = excluded.parsed_brand, size_base = excluded.size_base,
                      size_unit = excluded.size_unit, pack_qty = excluded.pack_qty,
                      is_active = true, last_seen_at = now()
                    returning id""",
                (retailer_id, p.external_id, p.url, p.name, p.brand, p.category, p.raw_ean, p.ean,
                 p.image_url, normalize_text(p.name), normalize_text(p.brand) if p.brand else None,
                 p.size_base, p.size_unit, p.pack_qty))
            rp_id = cur.fetchone()[0]
            stats["listings"] += 1

            # Convención: price = lo que paga el cliente; list_price = precio regular si hay oferta.
            price = p.sale_price or p.regular_price
            list_price = p.regular_price if p.sale_price else None
            total = (p.size_base or 0) * p.pack_qty
            unit_price = None
            if total:
                unit_price = round(price / total * (1000 if p.size_unit in ("g", "ml") else 1), 4)

            cur.execute(
                """select price, list_price, in_stock from price_history
                    where retailer_product_id = %s and store_id = %s
                    order by scraped_at desc limit 1""", (rp_id, store_id))
            last = cur.fetchone()
            if last and float(last[0]) == price and (float(last[1]) if last[1] is not None else None) == list_price \
                    and last[2] == p.in_stock:
                stats["prices_unchanged"] += 1
                continue
            cur.execute(
                """insert into price_history
                     (retailer_product_id, store_id, price, list_price, unit_price, in_stock)
                    values (%s,%s,%s,%s,%s,%s)""",
                (rp_id, store_id, price, list_price, unit_price, p.in_stock))
            stats["prices_inserted"] += 1

        cur.execute(
            """update scrape_runs set finished_at = now(), items_seen = %s, status = %s where id = %s""",
            (len(products), status, run_id))
    conn.commit()
    return stats


# ======================================================================
# CLI
# ======================================================================
def init_db(conn):
    """Crea automáticamente todas las tablas necesarias si no existen."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS retailers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                slug VARCHAR(100) UNIQUE NOT NULL,
                website TEXT
            );

            CREATE TABLE IF NOT EXISTS stores (
                id SERIAL PRIMARY KEY,
                retailer_id INT REFERENCES retailers(id) ON DELETE CASCADE,
                external_id VARCHAR(255) NOT NULL,
                name TEXT,
                is_online BOOLEAN,
                CONSTRAINT stores_retailer_id_external_id_key UNIQUE (retailer_id, external_id)
            );

            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                retailer_id INT REFERENCES retailers(id) ON DELETE CASCADE,
                external_id VARCHAR(255) NOT NULL,
                name TEXT,
                category TEXT,
                brand TEXT,
                image_url TEXT,
                CONSTRAINT products_retailer_id_external_id_key UNIQUE (retailer_id, external_id)
            );

            CREATE TABLE IF NOT EXISTS retailer_products (
                id SERIAL PRIMARY KEY,
                retailer_id INT REFERENCES retailers(id) ON DELETE CASCADE,
                product_id INT REFERENCES products(id) ON DELETE CASCADE,
                external_id VARCHAR(255),
                url TEXT,
                raw_name TEXT,
                raw_brand TEXT,
                raw_category TEXT,
                raw_ean TEXT,
                ean TEXT,
                image_url TEXT,
                normalized_name TEXT,
                parsed_brand TEXT,
                size_base NUMERIC(12, 2),
                size_unit VARCHAR(50),
                pack_qty INT DEFAULT 1,
                is_active BOOLEAN DEFAULT TRUE,
                last_seen_at TIMESTAMP,
                CONSTRAINT retailer_products_retailer_id_product_id_key UNIQUE (retailer_id, external_id)
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id SERIAL PRIMARY KEY,
                retailer_product_id INT REFERENCES retailer_products(id) ON DELETE CASCADE,
                store_id INT REFERENCES stores(id) ON DELETE CASCADE,
                price NUMERIC(12, 2) NOT NULL,
                list_price NUMERIC(12, 2),
                unit_price NUMERIC(12, 4),
                in_stock BOOLEAN,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS scrape_runs (
                id SERIAL PRIMARY KEY,
                retailer_id INT REFERENCES retailers(id) ON DELETE CASCADE,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                finished_at TIMESTAMP,
                status VARCHAR(50) DEFAULT 'running',
                items_count INT DEFAULT 0
            );
        """)
        conn.commit()


def main() -> int:
    ap = argparse.ArgumentParser(description="Scraper de Coto Digital")
    ap.add_argument("--category-url", action="append", help="URL de categoría (repetible)")
    ap.add_argument("--max-pages", type=int, default=50)
    ap.add_argument("--delay-min", type=float, default=2.0)
    ap.add_argument("--delay-max", type=float, default=4.5)
    ap.add_argument("--headed", action="store_true", help="mostrar el navegador")
    ap.add_argument("--dry-run", action="store_true", help="no escribe en la base; imprime resultados")
    ap.add_argument("--debug-dir", type=Path, help="guarda los JSON crudos capturados")
    ap.add_argument("--db-url", default=os.environ.get("DATABASE_URL"))
    args = ap.parse_args()

    if not args.dry_run and not args.db_url:
        sys.exit("Falta DATABASE_URL (o usá --dry-run).")

    from playwright.sync_api import sync_playwright

    categories = args.category_url or DEFAULT_CATEGORIES
    all_products: dict[str, Product] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed, proxy=proxy_from_env())
        ctx = browser.new_context(locale="es-AR", timezone_id="America/Argentina/Buenos_Aires",
                                  viewport={"width": 1366, "height": 900},
                                  user_agent=make_user_agent(browser.version))
        # No descargar imágenes/fuentes/media: menos carga para el sitio y corrida más rápida
        ctx.route("**/*", lambda r: r.abort()
                  if r.request.resource_type in ("image", "font", "media") else r.continue_())
        page = ctx.new_page()
        cap = Capture(args.debug_dir)
        page.on("response", cap.on_response)
        for url in categories:
            if cap.blocked:
                break
            print(f"Categoría: {url}")
            for p in scrape_category(page, cap, url, args.max_pages, (args.delay_min, args.delay_max)):
                all_products.setdefault(p.external_id, p)
        browser.close()

    products = list(all_products.values())
    print(f"\nTotal: {len(products)} productos únicos")
    if not products:
        print("No se extrajo nada. Corré con --headed --debug-dir debug/ y revisá los JSON capturados "
              "para ajustar las listas de claves (NAME_KEYS, PRICE_KEYS, etc.).")
        return 3 if cap.blocked else 1

    if args.dry_run:
        for p in products[:15]:
            print(json.dumps(asdict(p), ensure_ascii=False))
        return 0

    import psycopg
    with psycopg.connect(args.db_url, prepare_threshold=None) as conn:
        init_db(conn)
        print(save_products(conn, products, "partial" if cap.blocked else "ok"))
    return 3 if cap.blocked else 0


if __name__ == "__main__":
    sys.exit(main())
