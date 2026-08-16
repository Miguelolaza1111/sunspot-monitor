import csv
import time
import random
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

URL = "https://www.sidc.be/SILSO/DATA/EISN/EISN_current.txt"
CSV_FILE = Path("eisn_history.csv")

# Lima = UTC-5
LIMA_OFFSET = timedelta(hours=-5)


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


def save_data(rows):
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)

    now_lima = now_utc + LIMA_OFFSET

    captured_utc = now_utc.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    captured_lima = now_lima.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    file_exists = CSV_FILE.exists()

    existing_rows = []

    if file_exists:
        with CSV_FILE.open(
            "r",
            newline="",
            encoding="utf-8"
        ) as f:
            existing_rows = list(csv.DictReader(f))

    latest = rows[-1]

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

    with CSV_FILE.open(
        "a",
        newline="",
        encoding="utf-8"
    ) as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow([
                "hora_lima",
                "eisn",
                "hora_utc",
                "fecha",
                "desviacion",
                "estaciones_usadas",
                "estaciones_disponibles",
            ])

        writer.writerow([
            captured_lima,
            latest["eisn"],
            captured_utc,
            latest["fecha"],
            latest["desviacion"],
            latest["estaciones_usadas"],
            latest["estaciones_disponibles"],
        ])

    print(
        f"Guardado | Lima: {captured_lima} | "
        f"EISN: {latest['eisn']} | "
        f"UTC: {captured_utc} | "
        f"Fecha SILSO: {latest['fecha']} | "
        f"Estaciones: "
        f"{latest['estaciones_usadas']}/"
        f"{latest['estaciones_disponibles']}"
    )


if __name__ == "__main__":
    data = get_silso_data()
    save_data(data)
