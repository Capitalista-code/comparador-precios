import os
import sys
import requests
import psycopg

URL_GRANOS = "https://granosar.lfcaucino.workers.dev/api/v1/pizarra"

def run():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("Error: Falta DATABASE_URL.")

    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    
    print("Consultando precios de granos...")
    try:
        resp = requests.get(URL_GRANOS, headers=headers, timeout=15)
        if resp.status_code == 200:
            json_data = resp.json()
            # Buscamos en la clave 'granos' o 'data' según la estructura de la API
            granos_dict = json_data.get("granos") or json_data.get("data") or {}
            
            if isinstance(granos_dict, dict) and len(granos_dict) > 0:
                with psycopg.connect(db_url) as conn:
                    with conn.cursor() as cur:
                        count = 0
                        for grain_name, details in granos_dict.items():
                            if isinstance(details, dict):
                                ars = details.get("ars_tn") or details.get("precio_ars")
                                usd = details.get("usd_tn") or details.get("precio_usd")
                                var = details.get("variacion_pct_vs_rueda_anterior") or details.get("variacion")
                                
                                cur.execute(
                                    """
                                    INSERT INTO grain_prices (grain_name, market, price_ars, price_usd, variation) 
                                    VALUES (%s, %s, %s, %s, %s)
                                    """,
                                    (str(grain_name).capitalize(), "Rosario / Pizarra", ars, usd, var)
                                )
                                count += 1
                    conn.commit()
                print(f"-> Granos guardados con éxito ({count} registros).")
            else:
                print("-> No se encontraron datos válidos en la respuesta de granos.")
        else:
            print(f"-> Error al conectar con granos.ar (Código: {resp.status_code})")
    except Exception as e:
        print(f"Error en módulo granos: {e}")

if __name__ == "__main__":
    run()
