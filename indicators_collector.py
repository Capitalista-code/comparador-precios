import os
import sys
import requests
import psycopg

URL_DOLAR = "https://dolarapi.com/v1/dolares"
URL_GRANOS = "https://api.granos.ar/pizarra/actual"

CITIES = [
    "CAPITAL FEDERAL", "LA PLATA", "CORDOBA", "ROSARIO", 
    "SANTA FE", "PARANA", "MENDOZA", "SAN MIGUEL DE TUCUMAN"
]

def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("Falta DATABASE_URL en las variables de entorno.")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # 1. Dólares
            print("Consultando dólares...")
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
                print(f"Error dólares: {e}")

            # 2. Granos (granos.ar)
            print("Consultando precios de granos en granos.ar...")
            try:
                resp = requests.get(URL_GRANOS, headers=headers, timeout=15)
                print(f"Código de respuesta granos.ar: {resp.status_code}")
                
                if resp.status_code == 200:
                    data = resp.json()
                    # Verificamos la estructura que devuelve
                    granos_dict = data.get("granos", data) # Intenta adaptarse por si la estructura cambia
                    
                    if isinstance(granos_dict, dict):
                        count = 0
                        for grain_name, details in granos_dict.items():
                            if isinstance(details, dict):
                                cur.execute(
                                    """
                                    INSERT INTO grain_prices (grain_name, market, price_ars, price_usd, variation)
                                    VALUES (%s, %s, %s, %s, %s)
                                    """,
                                    (
                                        str(grain_name).capitalize(),
                                        "Rosario / Pizarra",
                                        details.get("ars_tn", details.get("precio_ars")),
                                        details.get("usd_tn", details.get("precio_usd")),
                                        details.get("variacion_pct_vs_rueda_anterior", details.get("variacion"))
                                    )
                                )
                                count += 1
                        print(f"-> Se guardaron {count} registros de granos con éxito.")
                    else:
                        print("-> La respuesta de granos.ar no tiene el formato de diccionario esperado.")
                else:
                    print(f"-> Error en granos.ar. Respuesta: {resp.text[:200]}")
            except Exception as e:
                print(f"Excepción al consultar granos.ar: {e}")

            # 3. Combustibles
            print("Consultando combustibles...")
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
    print("¡Proceso completo!")

if __name__ == "__main__":
    main()
