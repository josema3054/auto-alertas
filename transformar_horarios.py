import json
from datetime import datetime, timedelta

# Función para convertir de ET a horario argentino
def et_to_arg_datetime(et_str):
    # Ejemplo: "Sun. Jul. 27 9:11 pm ET"
    dt = datetime.strptime(et_str.replace('ET', '').strip(), "%a. %b. %d %I:%M %p")
    # ET = UTC-4, Argentina = UTC-3, sumar 1 hora
    dt_arg = dt + timedelta(hours=1)
    return dt_arg

with open("partidos_hoy.json", "r", encoding="utf-8") as f:
    partidos = json.load(f)

for partido in partidos:
    if "hora" in partido:
        dt_arg = et_to_arg_datetime(partido["hora"])
        partido["fecha"] = dt_arg.strftime("%Y-%m-%d")
        partido["hora"] = dt_arg.strftime("%H:%M")

with open("partidos_hoy.json", "w", encoding="utf-8") as f:
    json.dump(partidos, f, ensure_ascii=False, indent=2)
