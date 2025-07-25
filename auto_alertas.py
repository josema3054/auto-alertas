"""
Script automatizado para scrapeo, guardado de partidos y envío de alertas por Telegram
"""


import os
import sys
import json
from datetime import datetime, timedelta
import time
import requests
from bs4 import BeautifulSoup
import re

# Importar TelegramNotifier y settings adaptados a la estructura actual
from telegram_notifier import TelegramNotifier
import settingspsautoalerta as settings

PARTIDOS_FILE = 'partidos_hoy.json'

URL = "https://contests.covers.com/consensus/topoverunderconsensus/mlb/expert"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

def scrape_partidos():
    """Scrapea los partidos y sus horas, devuelve lista de dicts"""
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')
    partidos = []
    # Buscar la tabla principal
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 5:
                texto = row.get_text(separator='|', strip=True)
                # Ejemplo de extracción: equipo1|equipo2|hora|porcentaje|tipo
                equipos = re.findall(r'([A-Z]{2,3})', texto)
                hora = re.search(r'(\d{1,2}:\d{2}\s*[ap]m)', texto, re.IGNORECASE)
                porcentaje = re.search(r'(\d{1,3})\s*%\s*(Over|Under)', texto, re.IGNORECASE)
                if equipos and hora and porcentaje:
                    partidos.append({
                        'equipos': equipos,
                        'hora': hora.group(1),
                        'porcentaje': int(porcentaje.group(1)),
                        'tipo': porcentaje.group(2).capitalize(),
                        'texto': texto
                    })
    return partidos

def guardar_partidos(partidos):
    with open(PARTIDOS_FILE, 'w', encoding='utf-8') as f:
        json.dump(partidos, f, ensure_ascii=False, indent=2)
    print(f"✅ Partidos guardados en {PARTIDOS_FILE}")

def cargar_partidos():
    if not os.path.exists(PARTIDOS_FILE):
        return []
    with open(PARTIDOS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def hora_a_datetime(hora_str):
    # Convierte '7:05 pm' a datetime de hoy
    hoy = datetime.now().date()
    try:
        dt = datetime.strptime(hora_str.strip().lower().replace('pm', 'PM').replace('am', 'AM'), '%I:%M %p')
        return datetime.combine(hoy, dt.time())
    except Exception:
        return None

def enviar_alerta(partido):
    notifier = TelegramNotifier(settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID)
    mensaje = f"ALERTA MLB\nPartido: {' vs '.join(partido['equipos'])}\nHora: {partido['hora']}\nConsenso: {partido['porcentaje']}% {partido['tipo']}"
    notifier.send_message_sync(mensaje)
    print(f"🚨 Alerta enviada: {mensaje}")

def enviar_alerta_scrapeo(partido):
    notifier = TelegramNotifier(settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID)
    mensaje = f"SOLO SCRAPEO\nPartido: {' vs '.join(partido['equipos'])}\nHora: {partido['hora']}\nConsenso: {partido['porcentaje']}% {partido['tipo']}"
    notifier.send_message_sync(mensaje)
    print(f"📋 Scrapeo enviado: {mensaje}")

def main():
    print("Scrapeando partidos y guardando horas...")
    partidos = scrape_partidos()
    for partido in partidos:
        partido['alertado'] = False
    guardar_partidos(partidos)
    for partido in partidos:
        enviar_alerta_scrapeo(partido)
    print("Esperando partidos próximos para alerta...")
    fecha_ultimo_scrapeo = datetime.now().date()
    scrapeo_realizado_hoy = True
    while True:
        ahora = datetime.now()
        # Si es un nuevo día y son las 7:00 am o más, hacer nuevo scraping y enviar todos los partidos
        if ahora.date() != fecha_ultimo_scrapeo and ahora.hour >= 7 and not scrapeo_realizado_hoy:
            print("Nuevo día detectado. Scrapeando partidos a las 7am...")
            partidos = scrape_partidos()
            for partido in partidos:
                partido['alertado'] = False
            guardar_partidos(partidos)
            for partido in partidos:
                enviar_alerta_scrapeo(partido)
            fecha_ultimo_scrapeo = ahora.date()
            scrapeo_realizado_hoy = True
        elif ahora.date() != fecha_ultimo_scrapeo and ahora.hour < 7:
            # Esperar hasta las 7am para hacer el scraping
            scrapeo_realizado_hoy = False
        partidos = cargar_partidos()
        cambios = False
        for partido in partidos:
            dt = hora_a_datetime(partido['hora'])
            if not dt:
                continue
            minutos = (dt - ahora).total_seconds() / 60
            if 14 <= minutos <= 16 and not partido.get('alertado', False):
                print(f"Re-escrapeando antes de partido {' vs '.join(partido['equipos'])}...")
                nuevos_partidos = scrape_partidos()
                partido_actualizado = None
                for p in nuevos_partidos:
                    if p['equipos'] == partido['equipos'] and p['hora'] == partido['hora']:
                        partido_actualizado = p
                        break
                if partido_actualizado:
                    enviar_alerta(partido_actualizado)
                else:
                    enviar_alerta(partido)
                partido['alertado'] = True
                cambios = True
        if cambios:
            guardar_partidos(partidos)
        time.sleep(60)  # Revisar cada minuto

if __name__ == "__main__":
    main()
