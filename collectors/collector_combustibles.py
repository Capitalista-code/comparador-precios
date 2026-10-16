import os
import sys
import requests
import psycopg

CITIES = [
    "CAPITAL FEDERAL", "LA PLATA", "CORDOBA", "ROSARIO", 
    "SANTA FE", "PARANA", "MENDOZA", "SAN MIGUEL DE TUCUMAN"
]

def run():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("Error: Falta DATABASE_URL.")

    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    
    print("Consultando combustibles...")
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                for city in CITIES:
                    try:
                        url_fuel = f"https://naftas.com.ar/api/fuel?city={city.replace(' ', '%20')}"
                        resp = requests.get(url_fuel, headers=headers, timeout=10)
                        if resp.status_code == 200:
                            data = resp.json()
                            for city_name, city_info in data.items():
                                for company, fuels in city_info.get("empresas", {}).items():
                                    for fuel_type, details in fuels.items():
                                        cur.execute(
                                            """
                                            INSERT INTO fuel_prices (city, company, fuel_type, price, valid_date) 
                                            VALUES (%s, %s, %s, %s, %s)
                                            """,
                                            (city_name, company, fuel_type, details.get("precio"), details.get("fecha_vigencia"))
                                        )
                            print(f"-> Combustibles de {city} guardados con éxito.")
                    except Exception as e:
                        print(f"Error procesando combustibles para {city}: {e}")
            conn.commit()
        print("-> Módulo de combustibles finalizado.")
    except Exception as e:
        print(f"Error general en módulo combustibles: {e}")

if __name__ == "__main__":
    run()
