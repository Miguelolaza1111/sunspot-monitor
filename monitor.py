import csv
import time
import random
import urllib.request
import urllib.parse
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

URL = "https://www.sidc.be/SILSO/DATA/EISN/EISN_current.txt"
CSV_FILE = Path("eisn_history.csv")

# Lima = UTC-5
LIMA_OFFSET = timedelta(hours=-5)

# Cantidad máxima de registros que se conservarán
MAX_REGISTROS = 10


def get_silso_data():
    max_attempts = 6

    # Esperas progresivas entre intentos
    wait_times = [5, 10, 20, 30, 45]

    for attempt in range(1, max_attempts + 1):
        try:
            request = urllib.request.Request(
                URL,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 "
                        "(compatible; sunspot-monitor/1.0)"
                    ),
                    "Accept": "text/plain,*/*",
                    "Connection": "close",
                },
            )

            with urllib.request.urlopen(
                request,
                timeout=20
            ) as response:
                text = response.read().decode("utf-8")

            rows = []

            for line in text.splitlines():
                line = line.strip()

                if not line or line.startswith("#"):
                    continue

                parts = line.split()

                if len(parts) < 8:
                    continue

                try:
                    year = int(parts[0])
                    month = int(parts[1])
                    day = int(parts[2])
                    decimal_date = float(parts[3])
                    eisn = int(parts[4])
                    stddev = float(parts[5])
                    stations_used = int(parts[6])
                    stations_available = int(parts[7])
                except ValueError:
                    continue

                rows.append({
                    "fecha": f"{year:04d}-{month:02d}-{day:02d}",
                    "fecha_decimal": decimal_date,
                    "eisn": eisn,
                    "desviacion": stddev,
                    "estaciones_usadas": stations_used,
                    "estaciones_disponibles": stations_available,
                })

            if not rows:
                raise RuntimeError(
                    "SILSO respondió, pero no se encontraron "
                    "datos válidos."
                )

            print(
                "Datos de SILSO obtenidos correctamente "
                f"en el intento {attempt}."
            )

            return rows

        except Exception as e:
            print(
                f"Intento {attempt}/{max_attempts} fallido "
                f"al conectar con SILSO: {e}"
            )

            if attempt < max_attempts:
                wait = wait_times[attempt - 1]
                jitter = random.randint(0, 5)
                total_wait = wait + jitter

                print(
                    f"Esperando {total_wait} segundos "
                    "antes de volver a intentar..."
                )

                time.sleep(total_wait)

            else:
                raise RuntimeError(
                    "No fue posible obtener los datos de SILSO "
                    f"después de {max_attempts} intentos."
                ) from e


def send_telegram_message(latest, captured_lima):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print(
            "Telegram no configurado: faltan "
            "TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID."
        )
        return

    message = (
        "☀️ Nuevo dato EISN de SILSO\n\n"
        f"EISN: {latest['eisn']}\n"
        f"Fecha y hora Lima: {captured_lima}\n"
        f"D: {latest['desviacion']}   "
        f"E: {latest['estaciones_usadas']}/"
        f"{latest['estaciones_disponibles']}"
    )

    url = (
        f"https://api.telegram.org/bot{token}/sendMessage"
    )

    data = (
        f"chat_id={urllib.parse.quote(str(chat_id))}"
        f"&text={urllib.parse.quote(message)}"
    ).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": (
                "application/x-www-form-urlencoded"
            )
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=20
        ) as response:
            result = response.read().decode("utf-8")

        if '"ok":true' in result:
            print("Mensaje de Telegram enviado correctamente.")
        else:
            print(
                "Telegram respondió con un resultado inesperado: "
                f"{result}"
            )

    except Exception as e:
        print(
            f"No fue posible enviar el mensaje de Telegram: {e}"
        )


def save_data(rows):
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)

    now_lima = now_utc + LIMA_OFFSET

    captured_utc = now_utc.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    captured_lima = now_lima.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    existing_rows = []

    # Leer histórico existente
    if CSV_FILE.exists():
        with CSV_FILE.open(
            "r",
            newline="",
            encoding="utf-8"
        ) as f:
            existing_rows = list(csv.DictReader(f))

    latest = rows[-1]

    # Comprobar si el dato de SILSO cambió
    if existing_rows:
        last = existing_rows[-1]

        # Comparamos únicamente los datos de SILSO.
        # La hora de captura no provoca una fila duplicada.
        if (
            last.get("fecha") == latest["fecha"]
            and last.get("eisn") == str(latest["eisn"])
            and last.get("desviacion")
            == str(latest["desviacion"])
            and last.get("estaciones_usadas")
            == str(latest["estaciones_usadas"])
            and last.get("estaciones_disponibles")
            == str(latest["estaciones_disponibles"])
        ):
            print(
                "El dato de SILSO no ha cambiado. "
                "No se añade una nueva fila."
            )
            return

    # Crear el nuevo registro
    new_row = {
        "hora_lima": captured_lima,
        "eisn": str(latest["eisn"]),
        "hora_utc": captured_utc,
        "fecha": latest["fecha"],
        "desviacion": str(latest["desviacion"]),
        "estaciones_usadas": str(
            latest["estaciones_usadas"]
        ),
        "estaciones_disponibles": str(
            latest["estaciones_disponibles"]
        ),
    }

    # Añadir el nuevo registro
    existing_rows.append(new_row)

    # Conservar solamente los últimos 10 registros
    existing_rows = existing_rows[-MAX_REGISTROS:]

    # Reescribir el archivo completo
    with CSV_FILE.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as f:
        fieldnames = [
            "hora_lima",
            "eisn",
            "hora_utc",
            "fecha",
            "desviacion",
            "estaciones_usadas",
            "estaciones_disponibles",
        ]

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(existing_rows)

    print(
        f"Guardado | Lima: {captured_lima} | "
        f"EISN: {latest['eisn']} | "
        f"UTC: {captured_utc} | "
        f"Fecha SILSO: {latest['fecha']} | "
        f"Estaciones: "
        f"{latest['estaciones_usadas']}/"
        f"{latest['estaciones_disponibles']}"
    )

    print(
        f"Histórico limitado a los últimos "
        f"{MAX_REGISTROS} registros."
    )

    # Enviar Telegram solamente cuando se detectó
    # y guardó un cambio real en SILSO.
    send_telegram_message(
        latest,
        captured_lima
    )


if __name__ == "__main__":
    data = get_silso_data()
    save_data(data)
