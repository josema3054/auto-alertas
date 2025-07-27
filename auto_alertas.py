"""
Script automatizado para scrapeo, guardado de partidos y envío de alertas por Telegram
"""


import os
import sys
import json
from datetime import datetime, timedelta
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import re

# Importar TelegramNotifier y settings adaptados a la estructura actual
from telegram_notifier import TelegramNotifier
import settingspsautoalerta as settings

PARTIDOS_FILE = 'partidos_hoy.json'

def get_url_fecha():
    hoy = datetime.now().date()
    return f"https://contests.covers.com/consensus/topoverunderconsensus/mlb/expert/{hoy.strftime('%Y-%m-%d')}"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Referer': 'https://contests.covers.com/',
    'Cookie': 'consent=1;'
}

def scrape_partidos():
    """Scrapea los partidos y sus horas, devuelve lista de dicts"""
    url = get_url_fecha()
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    time.sleep(5)  # Espera para que cargue el JS
    html = driver.page_source
    driver.quit()
    soup = BeautifulSoup(html, 'html.parser')
    partidos = []
    # Buscar filas de la tabla de consenso
    filas = soup.find_all('tr')
    for fila in filas:
        celdas = fila.find_all('td')
        if not celdas or len(celdas) < 1:
            continue
        # Extraer equipos
        matchup_td = None
        for td in celdas:
            if td.find('span', class_='covers-CoversConsensus-table--teamBlock'):
                matchup_td = td
                break
        if not matchup_td:
            continue
        eq1_tag = matchup_td.find('span', class_='covers-CoversConsensus-table--teamBlock')
        eq2_tag = matchup_td.find('span', class_='covers-CoversConsensus-table--teamBlock2')
        equipo1 = eq1_tag.find('a').get_text(strip=True) if eq1_tag and eq1_tag.find('a') else ''
        equipo2 = eq2_tag.find('a').get_text(strip=True) if eq2_tag and eq2_tag.find('a') else ''
        if not equipo1 or not equipo2:
            continue
        deporte = 'MLB'
        # Hora (si existe en otra celda)
        hora = ''
        for celda in celdas:
            # Busca la celda que contiene 'pm ET' o 'am ET'
            texto = celda.get_text(separator=' ', strip=True)
            if re.search(r'(am|pm) ET', texto):
                hora = texto
                break
        # Porcentajes Over/Under y picks
        porc_under = porc_over = None
        # Asigna correctamente los porcentajes según el texto
        for celda in celdas:
            porc_tags = celda.find_all('span')
            for porc_tag in porc_tags:
                porc_text = porc_tag.get_text(strip=True)
                porc_val = int(re.findall(r'\d+', porc_text)[0]) if re.findall(r'\d+', porc_text) else None
                if 'Over' in porc_text:
                    porc_over = porc_val
                elif 'Under' in porc_text:
                    porc_under = porc_val
        # Picks: suma de los dos números en la celda correspondiente
        # Extraer el total y los picks según la posición de las celdas
        total = ''
        total_expertos = 0
        if len(celdas) >= 5:
            # El cuarto <td> es el total
            total = celdas[3].get_text(strip=True)
            # El quinto <td> son los picks (ejemplo: 5<br>3)
            picks_celda = celdas[4]
            picks = picks_celda.get_text(separator='|', strip=True).split('|')
            if len(picks) == 2 and picks[0].isdigit() and picks[1].isdigit():
                total_expertos = int(picks[0]) + int(picks[1])
        partido = {
            'deporte': deporte,
            'equipo1': equipo1,
            'equipo2': equipo2,
            'hora': hora,
            'porcentaje_under': porc_under,
            'porcentaje_over': porc_over,
            'total': total,
            'total_expertos': total_expertos
        }
        partidos.append(partido)
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
    mensaje = (
        f"Deporte: {partido.get('deporte', 'MLB')}\n"
        f"Partido: {partido.get('equipo1', '')} vs {partido.get('equipo2', '')}\n"
        f"Hora: {partido.get('hora', '')}\n"
        f"Total: {partido.get('total', '')}\n"
        f"Under: {partido.get('porcentaje_under', '')}%\n"
        f"Over: {partido.get('porcentaje_over', '')}%\n"
        f"Total picks: {partido.get('total_expertos', '')}"
    )
    notifier.send_message_sync(mensaje)
    print(f"🚨 Alerta enviada: {mensaje}")

def enviar_alerta_scrapeo(partido):
    notifier = TelegramNotifier(settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID)
    mensaje = (
        f"SOLO SCRAPEO\n"
        f"Deporte: {partido.get('deporte', 'MLB')}\n"
        f"Partido: {partido.get('equipo1', '')} vs {partido.get('equipo2', '')}\n"
        f"Hora: {partido.get('hora', '')}\n"
        f"Total: {partido.get('total', '')}\n"
        f"Under: {partido.get('porcentaje_under', '')}%\n"
        f"Over: {partido.get('porcentaje_over', '')}%\n"
        f"Total picks: {partido.get('total_expertos', '')}"
    )
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
    def normalizar(texto):
        return texto.strip().lower() if isinstance(texto, str) else ''

    while True:
        ahora = datetime.now()
        # Si es un nuevo día y son las 7:00 am o más, hacer nuevo scraping y enviar todos los partidos
        if ahora.date() != fecha_ultimo_scrapeo and ahora.hour >= 7 and not scrapeo_realizado_hoy:
            print(f"[{ahora.strftime('%H:%M:%S')}] Nuevo día detectado. Scrapeando partidos a las 7am...")
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
        # Solo hacer un scrapeo si hay partidos en rango
        partidos_en_rango = [p for p in partidos if (dt := hora_a_datetime(p['hora'])) and 14 <= (dt - ahora).total_seconds() / 60 <= 16 and not p.get('alertado', False)]
        nuevos_partidos = []
        if partidos_en_rango:
            print(f"[{ahora.strftime('%H:%M:%S')}] Re-escrapeando para partidos próximos...")
            nuevos_partidos = scrape_partidos()
        for partido in partidos:
            dt = hora_a_datetime(partido['hora'])
            if not dt:
                continue
            minutos = (dt - ahora).total_seconds() / 60
            if 14 <= minutos <= 16 and not partido.get('alertado', False):
                print(f"[{ahora.strftime('%H:%M:%S')}] Re-escrapeando: {partido['equipo1']} vs {partido['equipo2']}")
                partido_actualizado = None
                for p in nuevos_partidos:
                    if (normalizar(p.get('equipo1')) == normalizar(partido.get('equipo1')) and
                        normalizar(p.get('equipo2')) == normalizar(partido.get('equipo2')) and
                        normalizar(p.get('hora')) == normalizar(partido.get('hora'))):
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
