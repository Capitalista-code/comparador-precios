import os
import sys
import requests
import psycopg

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

        json_resp = resp.json()
        data_root = json_resp.get("data", {})
        granos_dict = data_root.get("granos", {})

        if not granos_dict:
            print("-> La API no devolvió datos de granos.")
            return

        datos_a_guardar = []
        for nombre_grano, info in granos_dict.items():
            grain_name = nombre_grano.capitalize()
            market = "BCR - Pizarra"
            price_ars = info.get("ars_tn")
            price_usd = info.get("usd_tn")
            variation = info.get("variacion_pct_vs_rueda_anterior")

            datos_a_guardar.append({
                "grain_name": grain_name,
                "market": market,
                "price_ars": float(price_ars) if price_ars is not None else None,
                "price_usd": float(price_usd) if price_usd is not None else None,
                "variation": float(variation) if variation is not None else 0.0
            })

        # Guardar en Supabase con la estructura que espera la App
        if datos_a_guardar:
            with psycopg.connect(db_url) as conn:
                with conn.cursor() as cur:
                    for item in datos_a_guardar:
                        cur.execute(
                            """
                            INSERT INTO grain_prices (grain_name, market, price_ars, price_usd, variation)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (
                                item["grain_name"],
                                item["market"],
                                item["price_ars"],
                                item["price_usd"],
                                item["variation"]
                            )
                        )
                conn.commit()
            print("-> Datos de granos guardados con éxito para Streamlit.")
        else:
            print("-> No se encontraron datos para insertar.")

    except Exception as e:
        print(f"Error en módulo granos: {e}")

if __name__ == "__main__":
    run()
