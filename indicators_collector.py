import os
import sys
import requests
import psycopg

URL_DOLAR = "https://dolarapi.com/v1/dolares"
URL_GRANOS = "https://granosar.lfcaucino.workers.dev/api/v1/pizarra"

CITIES = [
    "CAPITAL FEDERAL", "LA PLATA", "CORDOBA", "ROSARIO", 
    "SANTA FE", "PARANA", "MENDOZA", "SAN MIGUEL DE TUCUMAN"
]

def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("Error: Falta la variable de entorno DATABASE_URL.")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            
            # 1. Dólares
            try:
                resp = requests.get(URL_DOLAR, headers=headers, timeout=10)
                if resp.status_code == 200:
                    for item in resp.json():
                        cur.execute(
                            "INSERT INTO economic_indicators (indicator_type, name, buy_price, sell_price) VALUES (%s, %s, %s, %s)",
                            (item.get("casa"), item.get("nombre"), item.get("compra"), item.get("venta"))
                        )
                    print("-> Dólares guardados con éxito.")
            except Exception as e:
                print(f"Error en dólares: {e}")

            # 2. Granos (Analizador universal y blindado)
            try:
                resp = requests.get(URL_GRANOS, headers=headers, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    items_to_process = []
                    
                    # Normalizamos cualquier estructura JSON (lista, dict anidado, etc.)
                    if isinstance(data, list):
                        items_to_process = data
                    elif isinstance(data, dict):
                        # Buscamos dentro de 'data', 'granos' o usamos el dict raíz
                        container = data.get("data") or data.get("granos") or data
                        if isinstance(container, dict):
                            for k, v in container.items():
                                if isinstance(v, dict):
                                    v["_key_name"] = k
                                    items_to_process.append(v)
                        elif isinstance(container, list):
                            items_to_process = container

                    count = 0
                    for item in items_to_process:
                        if isinstance(item, dict):
                            name = item.get("nombre") or item.get("grano") or item.get("grain") or item.get("_key_name")
                            
                            # Filtramos llaves contenedoras o metadatos que no sean cultivos
                            if not name or str(name).lower() in ["data", "granos", "pizarra", "fecha", "status", "version", "meta"]:
                                continue
                                
                            ars = item.get("ars_tn") or item.get("precio_ars") or item.get("precio") or item.get("ars")
                            usd = item.get("usd_tn") or item.get("precio_usd") or item.get("usd")
                            var = item.get("variacion_pct_vs_rueda_anterior") or item.get("variacion") or item.get("var")
                            
                            cur.execute(
                                """
                                INSERT INTO grain_prices (grain_name, market, price_ars, price_usd, variation)
                                VALUES (%s, %s, %s, %s, %s)
                                """,
                                (str(name).capitalize(), "Rosario / Pizarra", ars, usd, var)
                            )
                            count += 1
                    print(f"-> Granos guardados con éxito ({count} registros).")
            except Exception as e:
                print(f"Error en granos: {e}")

            # 3. Combustibles
            for city in CITIES:
                try:
                    url_fuel = f"https://naftas.com.ar/api/fuel?city={city.replace(' ', '%20')}"
                    resp = requests.get(url_fuel, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        for city_name, city_info in resp.json().items():
                            for company, fuels in city_info.get("empresas", {}).items():
                                for fuel_type, details in fuels.items():
                                    cur.execute(
                                        "INSERT INTO fuel_prices (city, company, fuel_type, price, valid_date) VALUES (%s, %s, %s, %s, %s)",
                                        (city_name, company, fuel_type, details.get("precio"), details.get("fecha_vigencia"))
                                    )
                except Exception as e:
                    print(f"Error combustibles {city}: {e}")

        conn.commit()
    print("¡Proceso finalizado!")

if __name__ == "__main__":
    main()
