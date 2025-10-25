from flask import Flask, render_template, request, redirect, url_for, send_file, flash, send_from_directory
from datetime import datetime
from openai import OpenAI
from PIL import Image
import csv
from dotenv import load_dotenv
import os
import base64
import pytesseract

app = Flask(__name__)
app.secret_key = "superclave"

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "data", "registros.csv")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")

os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

CSV_HEADER = ["id", "fecha_hora", "matricula", "propietario", "tipo_vehiculo", "observacion", "imagen"]

def ensure_csv():
    if not os.path.exists(DATA_PATH):
        with open(DATA_PATH, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADER)

def read_csv():
    ensure_csv()
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    return reader

def write_csv(rows):
    with open(DATA_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(rows)

# === OCR con GPT-4o ===
def extract_plate_from_image(image_path):
    try:
        with open(image_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extrae únicamente el texto de la matrícula visible "
                                "en esta imagen (placa de vehículo). Devuelve solo la matrícula, "
                                "sin texto adicional, comentarios ni símbolos extras."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}"
                            },
                        },
                    ],
                }
            ],
        )

        text = response.choices[0].message.content.strip().upper()
        clean = "".join([c for c in text if c.isalnum() or c == "-"])[:10]
        return clean or "NO_DETECTADA"

    except Exception as e:
        print(" Error OCR con OpenAI:", e)
        return "NO_DETECTADA"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/guardar", methods=["POST"])
def guardar():
    ensure_csv()
    file = request.files.get("imagen")
    propietario = request.form.get("propietario", "")
    tipo = request.form.get("tipo_vehiculo", "")
    obs = request.form.get("observacion", "")

    if not file:
        flash("⚠️ Debes subir una imagen", "error")
        return redirect(url_for("index"))

    filename = f"matricula_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    path = os.path.join(UPLOADS_DIR, filename)
    file.save(path)

    # Intentar leer con GPT-4o
    matricula = extract_plate_from_image(path)

    # Fallback con pytesseract
    if matricula == "NO_DETECTADA":
        image = Image.open(path)
        ocr_text = pytesseract.image_to_string(image, lang="eng")
        ocr_text = ocr_text.strip().replace(" ", "").replace("\n", "").upper()
        matricula = "".join([c for c in ocr_text if c.isalnum() or c == "-"])[:10]

    rows = read_csv()
    new_id = str(len(rows) + 1)
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows.append({
        "id": new_id,
        "fecha_hora": fecha,
        "matricula": matricula,
        "propietario": propietario,
        "tipo_vehiculo": tipo,
        "observacion": obs,
        "imagen": filename
    })
    write_csv(rows)

    flash("✅ Registro guardado correctamente", "ok")
    return redirect(url_for("index"))

@app.route("/registros")
def registros():
    data = read_csv()
    return render_template("registros.html", registros=data)

@app.route("/eliminar/<id>")
def eliminar(id):
    rows = read_csv()
    filtered = [r for r in rows if r["id"] != id]
    deleted = [r for r in rows if r["id"] == id]
    if deleted:
        img = deleted[0]["imagen"]
        img_path = os.path.join(UPLOADS_DIR, img)
        if os.path.exists(img_path):
            os.remove(img_path)
    write_csv(filtered)
    flash("Registro eliminado correctamente", "ok")
    return redirect(url_for("registros"))

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOADS_DIR, filename)

@app.route("/descargar")
def descargar():
    ensure_csv()
    return send_file(DATA_PATH, as_attachment=True, download_name="registros.csv")

if __name__ == "__main__":
    app.run(debug=True)
