import os
import sys
import requests
import psycopg

URL_DOLAR = "https://dolarapi.com/v1/dolares"

def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("Falta DATABASE_URL en las variables de entorno.")

    print("Consultando cotizaciones de dólares...")
    response = requests.get(URL_DOLAR, timeout=10)
    response.raise_for_status()
    data = response.json()

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            for item in data:
                casa = item.get("casa")
                nombre = item.get("nombre")
                compra = item.get("compra")
                venta = item.get("venta")

                cur.execute(
                    """
                    INSERT INTO economic_indicators (indicator_type, name, buy_price, sell_price)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (casa, nombre, compra, venta)
                )
        conn.commit()
    print(f"¡Se guardaron {len(data)} indicadores correctamente en Supabase!")

if __name__ == "__main__":
    main()
