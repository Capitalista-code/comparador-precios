import os
import sys
import requests

def run():
    url = "https://bna.com.ar/Personas"
    
    print("=== PRUEBA DE CONECTIVIDAD BNA ===")
    print(f"Intentando conectar a: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        print(f"-> Status Code recibido: {resp.status_code}")
        print(f"-> Longitud del contenido recibido: {len(resp.text)} caracteres")
        print(f"-> Primeros 300 caracteres de la respuesta:")
        print(resp.text[:300])
        
    except Exception as e:
        print(f"-> EXCEPCIÓN AL CONECTAR CON BNA: {e}")
        
    print("=== FIN DE PRUEBA ===")

if __name__ == "__main__":
    run()
