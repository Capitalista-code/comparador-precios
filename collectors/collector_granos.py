import os
import sys
import requests

def run():
    # URL que estábamos probando
    url = "https://granosar.lfcaucino.workers.dev/api/v1/pizarra"
    
    print("=== INICIO DE DIAGNÓSTICO DE GRANOS ===")
    print(f"Intentando conectar a: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        print(f"-> Status Code recibido: {resp.status_code}")
        print(f"-> Respuesta cruda del servidor (primeros 400 caracteres):")
        print(resp.text[:400])
        
    except Exception as e:
        print(f"-> EXCEPCIÓN CRÍTICA AL CONECTAR: {e}")
        
    print("=== FIN DE DIAGNÓSTICO ===")

if __name__ == "__main__":
    run()
