import os
import sys
import requests
import psycopg

URL_DOLAR = "https://dolarapi.com/v1/dolares"
URL_GRANOS = "https://api.granos.ar/pizarra/actual" # API pública de granos en Argentina

CITIES = [
    "CAPITAL FEDERAL", "LA PLATA", "CORDOBA", "ROSARIO", 
    "SANTA FE", "PARANA", "MENDOZA", "SAN MIGUEL DE TUCUMAN"
]

def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("Falta DATABASE_URL en las variables de entorno.")

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # 1. Dólares
            print("Consultando dólares...")
            try:
                resp = requests.get(URL_DOLAR, timeout=10)
                if resp.status_code == 200:
                    for item in resp.json():
                        cur.execute(
                            "INSERT INTO economic_indicators (indicator_type, name, buy_price, sell_price) VALUES (%s, %s, %s, %s)",
                            (item.get("casa"), item.get("nombre"), item.get("compra"), item.get("venta"))
                        )
            except Exception as e:
                print(f"Error dólares: {e}")

            # 2. Granos (Soja, Maíz, Trigo, etc.)
            print("Consultando precios de granos...")
            try:
                resp = requests.get(URL_GRANOS, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    granos_dict = data.get("granos", {})
                    for grain_name, details in granos_dict.items():
                        cur.execute(
                            """
                            INSERT INTO grain_prices (grain_name, market, price_ars, price_usd, variation)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (
                                grain_name.capitalize(),
                                "Rosario / Pizarra",
                                details.get("ars_tn"),
                                details.get("usd_tn"),
                                details.get("variacion_pct_vs_rueda_anterior")
                            )
                        )
                    print("-> Granos guardados con éxito.")
            except Exception as e:
                print(f"Error granos: {e}")

            # 3. Combustibles (Capitales principales)
            print("Consultando combustibles...")
            for city in CITIES:
                try:
                    url_fuel = f"https://naftas.com.ar/api/fuel?city={city.replace(' ', '%20')}"
                    resp = requests.get(url_fuel, timeout=10)
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
    print("¡Recolección completa!")

if __name__ == "__main__":
    main()
