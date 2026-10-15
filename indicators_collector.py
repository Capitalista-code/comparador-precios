import os
import sys
import requests
import psycopg

URL_DOLAR = "https://dolarapi.com/v1/dolares"
CITIES = ["SANTA FE", "ROSARIO", "PARANA", "CAPITAL FEDERAL"]

def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("Falta DATABASE_URL en las variables de entorno.")

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # 1. Recolectar Dólares
            print("Consultando cotizaciones de dólares...")
            resp_dolar = requests.get(URL_DOLAR, timeout=10)
            resp_dolar.raise_for_status()
            dolar_data = resp_dolar.json()

            for item in dolar_data:
                cur.execute(
                    """
                    INSERT INTO economic_indicators (indicator_type, name, buy_price, sell_price)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (item.get("casa"), item.get("nombre"), item.get("compra"), item.get("venta"))
                )
            print(f"-> Se guardaron {len(dolar_data)} indicadores de dólares.")

            # 2. Recolectar Combustibles
            print("Consultando precios de combustibles...")
            for city in CITIES:
                try:
                    url_fuel = f"https://naftas.com.ar/api/fuel?city={city.replace(' ', '%20')}"
                    resp_fuel = requests.get(url_fuel, timeout=10)
                    if resp_fuel.status_code == 200:
                        fuel_data = resp_fuel.json()
                        for city_name, city_info in fuel_data.items():
                            empresas = city_info.get("empresas", {})
                            for company, fuels in empresas.items():
                                for fuel_type, details in fuels.items():
                                    precio = details.get("precio")
                                    fecha_vigencia = details.get("fecha_vigencia")
                                    cur.execute(
                                        """
                                        INSERT INTO fuel_prices (city, company, fuel_type, price, valid_date)
                                        VALUES (%s, %s, %s, %s, %s)
                                        """,
                                        (city_name, company, fuel_type, precio, fecha_vigencia)
                                    )
                        print(f"-> Combustibles de {city} guardados correctamente.")
                except Exception as e:
                    print(f"Error consultando combustibles para {city}: {e}")

        conn.commit()
    print("¡Proceso de recolección completo!")

if __name__ == "__main__":
    main()
