import csv
import time
import random
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://www.sidc.be/SILSO/DATA/EISN/EISN_current.txt"
CSV_FILE = Path("eisn_history.csv")


def get_silso_data():
    # Número de intentos antes de considerar que SILSO no está disponible.
    max_attempts = 6

    # Esperas progresivas entre intentos.
    wait_times = [5, 10, 20, 30, 45]

    for attempt in range(1, max_attempts + 1):
        try:
            request = urllib.request.Request(
                URL,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; sunspot-monitor/1.0)",
                    "Accept": "text/plain,*/*",
                    "Connection": "close",
                },
            )

            with urllib.request.urlopen(request, timeout=20) as response:
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
                    "SILSO respondió, pero no se encontraron datos válidos."
                )

            print(
                f"Datos de SILSO obtenidos correctamente "
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

                # Añadimos una pequeña variación para que dos intentos
                # no se produzcan exactamente al mismo tiempo.
                jitter = random.randint(0, 5)
                total_wait = wait + jitter

                print(
                    f"Esperando {total_wait} segundos "
                    f"antes de volver a intentar..."
                )

                time.sleep(total_wait)

            else:
                raise RuntimeError(
                    "No fue posible obtener los datos de SILSO "
                    f"después de {max_attempts} intentos."
                ) from e


def save_data(rows):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    captured_at = now.isoformat().replace("+00:00", "Z")

    file_exists = CSV_FILE.exists()

    existing_rows = []

    if file_exists:
        with CSV_FILE.open(
            "r",
            newline="",
            encoding="utf-8"
        ) as f:
            existing_rows = list(csv.DictReader(f))

    # La última fila válida de SILSO corresponde al dato más reciente.
    latest = rows[-1]

    if existing_rows:
        last = existing_rows[-1]

        # Si todos los datos son exactamente iguales al último registro,
        # no añadimos una nueva línea.
        if (
            last["fecha"] == latest["fecha"]
            and last["eisn"] == str(latest["eisn"])
            and last["desviacion"] == str(latest["desviacion"])
            and last["estaciones_usadas"]
            == str(latest["estaciones_usadas"])
            and last["estaciones_disponibles"]
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
                "captura_utc",
                "fecha",
                "fecha_decimal",
                "eisn",
                "desviacion",
                "estaciones_usadas",
                "estaciones_disponibles",
            ])

        writer.writerow([
            captured_at,
            latest["fecha"],
            latest["fecha_decimal"],
            latest["eisn"],
            latest["desviacion"],
            latest["estaciones_usadas"],
            latest["estaciones_disponibles"],
        ])

    print(
        f"Guardado: {captured_at} | "
        f"{latest['fecha']} | "
        f"EISN {latest['eisn']} | "
        f"{latest['estaciones_usadas']}/"
        f"{latest['estaciones_disponibles']} estaciones"
    )


if __name__ == "__main__":
    data = get_silso_data()
    save_data(data)
