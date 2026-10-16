import os
import sys
import requests
import psycopg

URL_DOLAR = "https://dolarapi.com/v1/dolares"
URL_GRANOS = "https://granosar.lfcaucino.workers.dev/api/v1/pizarra"

CITIES = [
    "CAPITAL FEDERAL", "LA PLATA", "CORDOBA", "ROSARIO", 
    "SANTA FE", "PARANA", "MENDOZA", "SAN MIGUEL DE TUCUMAN"
]

def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("Error: Falta la variable de entorno DATABASE_URL.")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            
            # 1. Recolección de Dólares
            try:
                resp = requests.get(URL_DOLAR, headers=headers, timeout=10)
                if resp.status_code == 200:
                    for item in resp.json():
                        cur.execute(
                            """
                            INSERT INTO economic_indicators (indicator_type, name, buy_price, sell_price) 
                            VALUES (%s, %s, %s, %s)
                            """,
                            (item.get("casa"), item.get("nombre"), item.get("compra"), item.get("venta"))
                        )
                    print("-> Dólares guardados con éxito.")
            except Exception as e:
                print(f"Error al procesar dólares: {e}")

            # 2. Recolectar Granos (Corregido para entrar al nivel 'data')
            try:
                resp = requests.get(URL_GRANOS, headers=headers, timeout=15)
                if resp.status_code == 200:
                    json_data = resp.json()
                    
                    # Extraemos el diccionario interno de granos según la estructura de la API
                    granos_dict = json_data.get("data", json_data.get("granos", json_data))
                    
                    if isinstance(granos_dict, dict):
                        count = 0
                        for grain_name, details in granos_dict.items():
                            # Omitimos metadatos si los hubiera
                            if grain_name.lower() in ["fecha", "tipo_cambio", "meta", "version", "status"]:
                                continue
                                
                            if isinstance(details, dict):
                                ars = details.get("ars_tn") or details.get("precio_ars") or details.get("precio")
                                usd = details.get("usd_tn") or details.get("precio_usd")
                                var = details.get("variacion_pct_vs_rueda_anterior") or details.get("variacion")
                                
                                cur.execute(
                                    """
                                    INSERT INTO grain_prices (grain_name, market, price_ars, price_usd, variation)
                                    VALUES (%s, %s, %s, %s, %s)
                                    """,
                                    (
                                        str(grain_name).capitalize(),
                                        "Rosario / Pizarra",
                                        ars,
                                        usd,
                                        var
                                    )
                                )
                                count += 1
                        print(f"-> Granos guardados con éxito ({count} registros).")
                    else:
                        print("-> La estructura de granos no es un diccionario válido.")
                else:
                    print(f"-> No se pudo conectar a granos.ar (Código: {resp.status_code})")
            except Exception as e:
                print(f"Error al procesar granos: {e}")

            # 3. Recolectar Combustibles
            for city in CITIES:
                try:
                    url_fuel = f"https://naftas.com.ar/api/fuel?city={city.replace(' ', '%20')}"
                    resp = requests.get(url_fuel, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        for city_name, city_info in resp.json().items():
                            for company, fuels in city_info.get("empresas", {}).items():
                                for fuel_type, details in fuels.items():
                                    cur.execute(
                                        """
                                        INSERT INTO fuel_prices (city, company, fuel_type, price, valid_date) 
                                        VALUES (%s, %s, %s, %s, %s)
                                        """,
                                        (city_name, company, fuel_type, details.get("precio"), details.get("fecha_vigencia"))
                                    )
                        print(f"-> Combustibles de {city} guardados.")
                except Exception as e:
                    print(f"Error al procesar combustibles para {city}: {e}")

        conn.commit()
    print("¡Proceso de recolección finalizado correctamente!")

if __name__ == "__main__":
    main()
