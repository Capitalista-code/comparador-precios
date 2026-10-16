import os
import sys
import requests
import psycopg

URL_DOLAR = "https://dolarapi.com/v1/dolares"

def run():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("Error: Falta DATABASE_URL.")

    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    
    print("Consultando DolarAPI...")
    try:
        resp = requests.get(URL_DOLAR, headers=headers, timeout=10)
        if resp.status_code == 200:
            with psycopg.connect(db_url) as conn:
                with conn.cursor() as cur:
                    for item in resp.json():
                        cur.execute(
                            """
                            INSERT INTO economic_indicators (indicator_type, name, buy_price, sell_price) 
                            VALUES (%s, %s, %s, %s)
                            """,
                            (item.get("casa"), item.get("nombre"), item.get("compra"), item.get("venta"))
                        )
                conn.commit()
            print("-> Dólares guardados con éxito.")
    except Exception as e:
        print(f"Error en módulo dólares: {e}")

if __name__ == "__main__":
    run()
