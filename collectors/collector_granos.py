import os
import sys
import requests
import psycopg

# API especializada en granos de pizarra argentinos (datos oficiales de la BCR en JSON)
URL_API_GRANOS = "https://granosar.lfcaucino.workers.dev/api/v1/pizarra"

def run():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("Error: Falta DATABASE_URL.")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    print("Consultando API de precios de pizarra...")
    try:
        resp = requests.get(URL_API_GRANOS, headers=headers, timeout=15)
        if resp.status_code != 200:
            sys.exit(f"Error al conectar con la API (Status: {resp.status_code})")

        data = resp.json()
        print("-> Datos obtenidos con éxito de la API.")

        # Procesamos la respuesta JSON de la API
        # (Suele devolver una lista o un diccionario con los granos y sus precios)
        registros = data if isinstance(data, list) else data.get("results", data.get("data", []))
        
        if not registros:
            print("-> La API no devolvió registros en este momento.")
            return

        datos_a_guardar = []
        for item in registros:
            # Extraemos los campos estándar que provee la API
            commodity = item.get("grano") or item.get("commodity") or item.get("cultivo")
            price_ars = item.get("precio_ars") or item.get("price_ars") or item.get("pesos")
            price_usd = item.get("precio_usd") or item.get("price_usd") or item.get("dolares")
            source = item.get("source", "granos.ar (BCR)")

            if commodity:
                datos_a_guardar.append({
                    "commodity": commodity,
                    "price_ars": float(price_ars) if price_ars else None,
                    "price_usd": float(price_usd) if price_usd else None,
                    "source": source
                })

        print(f"-> Procesando {len(datos_a_guardar)} cultivos...")

        # Guardar en Supabase
        if datos_a_guardar:
            with psycopg.connect(db_url) as conn:
                with conn.cursor() as cur:
                    for item in datos_a_guardar:
                        cur.execute(
                            """
                            INSERT INTO grain_prices (commodity, price_ars, price_usd, source)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (item["commodity"], item["price_ars"], item["price_usd"], item["source"])
                        )
                conn.commit()
            print("-> Datos de granos guardados correctamente en Supabase.")
        else:
            print("-> No se encontraron datos válidos para insertar.")

    except Exception as e:
        print(f"Error en módulo granos API: {e}")

if __name__ == "__main__":
    run()
