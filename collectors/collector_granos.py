import os
import sys
import requests
import psycopg

URL_API_GRANOS = "https://granosar.lfcaucino.workers.dev/api/v1/pizarra"

def run():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("Error: Falta DATABASE_URL.")

    print("1. Conectando a la API de granos...")
    resp = requests.get(URL_API_GRANOS, timeout=15)
    print(f"-> Status API: {resp.status_code}")
    
    json_resp = resp.json()
    granos_dict = json_resp.get("data", {}).get("granos", {})
    
    if not granos_dict:
        print("-> No hay granos en el JSON.")
        return

    print("2. Intentando insertar en Supabase...")
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                for nombre_grano, info in granos_dict.items():
                    commodity = nombre_grano.capitalize()
                    price_ars = info.get("ars_tn")
                    price_usd = info.get("usd_tn")
                    source = "granos.ar (BCR)"

                    print(f"   Insertando: {commodity} | ARS: {price_ars} | USD: {price_usd}")
                    cur.execute(
                        """
                        INSERT INTO grain_prices (commodity, price_ars, price_usd, source)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (commodity, price_ars, price_usd, source)
                    )
            conn.commit()
        print("-> ¡Inserción en Supabase exitosa!")
        
    except Exception as db_error:
        print(f"-> ¡ERROR CRÍTICO DE SUPABASE!: {db_error}")

if __name__ == "__main__":
    run()
