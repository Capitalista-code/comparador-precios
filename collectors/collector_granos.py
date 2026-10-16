import os
import sys
import re
import requests
from bs4 import BeautifulSoup
import psycopg

URL_BCR = "https://www.cac.bcr.com.ar/es/precios-de-pizarra"

def parse_monto(texto):
    """Limpia textos como '$ 560.000,00' o 'US$ 372,34' y devuelve un float."""
    if not texto or "S/C" in texto:
        return None
    # Elimina todo lo que no sea número o coma
    limpio = re.sub(r"[^\d,]", "", texto).replace(",", ".")
    try:
        return float(limpio)
    except ValueError:
        return None

def run():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("Error: Falta DATABASE_URL.")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    print("Consultando Precios de Pizarra de la Bolsa de Comercio de Rosario (BCR)...")
    try:
        resp = requests.get(URL_BCR, headers=headers, timeout=15)
        if resp.status_code != 200:
            sys.exit(f"Error al conectar con la BCR (Status: {resp.status_code})")

        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Mapeo de granos a buscar en el HTML
        granos = ["Trigo", "Maíz", "Girasol", "Soja", "Sorgo"]
        datos = []

        # Buscamos el texto de cada grano en la estructura del HTML
        for grano in granos:
            nodo = soup.find(text=re.compile(rf"^\s*{grano}\s*$", re.IGNORECASE))
            if nodo:
                contenedor = nodo.find_parent(["tr", "div", "li"]) or nodo.parent
                texto_bloque = contenedor.get_text(separator=" ")
                
                # Extraemos los montos en $ y en US$
                monto_ars = None
                monto_usd = None

                match_ars = re.search(r"\$\s*([\d\.\,]+)", texto_bloque)
                if match_ars:
                    monto_ars = parse_monto(match_ars.group(1))

                match_usd = re.search(r"US\$\s*([\d\.\,]+)", texto_bloque)
                if match_usd:
                    monto_usd = parse_monto(match_usd.group(1))

                if monto_ars is not None or monto_usd is not None:
                    datos.append({
                        "commodity": grano,
                        "price_ars": monto_ars,
                        "price_usd": monto_usd,
                        "source": "BCR - Cámara Arbitral"
                    })

        if not datos:
            print("-> Aviso: No se pudieron extraer datos de la tabla. Revisando estructura alternativa...")
            # Si el selector estricto falla, intentamos una búsqueda más amplia
            all_text = soup.get_text()
            for grano in granos:
                match = re.search(rf"{grano}\s+\$\s*([\d\.\,]+)\s+US\$\s*([\d\.\,]+)", all_text, re.IGNORECASE)
                if match:
                    datos.append({
                        "commodity": grano,
                        "price_ars": parse_monto(match.group(1)),
                        "price_usd": parse_monto(match.group(2)),
                        "source": "BCR - Cámara Arbitral"
                    })

        print(f"-> Granos encontrados: {len(datos)}")
        for item in datos:
            print(f"   * {item['commodity']}: ${item['price_ars']} / US${item['price_usd']}")

        # Guardar en Supabase
        if datos:
            with psycopg.connect(db_url) as conn:
                with conn.cursor() as cur:
                    for item in datos:
                        cur.execute(
                            """
                            INSERT INTO grain_prices (commodity, price_ars, price_usd, source)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (item["commodity"], item["price_ars"], item["price_usd"], item["source"])
                        )
                conn.commit()
            print("-> Datos guardados correctamente en Supabase.")
        else:
            print("-> No se insertaron registros (estructura HTML vacía o sin cotización).")

    except Exception as e:
        print(f"Error en módulo granos BCR: {e}")

if __name__ == "__main__":
    run()
