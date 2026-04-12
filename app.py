from flask import Flask, request, render_template_string
import pdfplumber
import numpy as np
import re

# OCR EKLİYORUZ
from PIL import Image
import pytesseract

app = Flask(__name__)


# ---------------- PDF → OCR + TEXT ----------------
def parse_pdf(file):

    text = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:

            # 1) normal text
            t = page.extract_text()
            if t:
                text += " " + t

            # 2) OCR (KRİTİK FIX)
            try:
                img = page.to_image(resolution=300).original
                ocr = pytesseract.image_to_string(img, lang="eng")
                text += " " + ocr
            except:
                pass

    if not text.strip():
        return None, {}, []

    # Beton sınıfı
    match = re.search(r"C(\d{2})/(\d{2})", text)

    fck = None
    if match:
        fck = int(match.group(2))

    # Sayılar
    numbers = re.findall(r"\d+\.\d+|\d+", text)

    values = []
    for n in numbers:
        try:
            v = float(str(n).replace(",", "."))
            if 10 < v < 120:
                values.append(v)
        except:
            pass

    return fck, {}, values


# ---------------- ANALİZ ----------------
def analyze(fck, values):

    if not values:
        return {"error": "OCR dahil hiçbir veri okunamadı"}

    if not fck:
        return {"error": "Beton sınıfı bulunamadı"}

    avg = np.mean(values)
    min_val = min(values)

    n = len(values)

    if n == 1:
        limit = fck
    elif n <= 4:
        limit = fck + 1
    else:
        limit = fck + 2

    status = "UYGUN"
    if avg < limit or min_val < fck - 4:
        status = "UYGUN DEĞİL"

    return {
        "fck": fck,
        "avg": round(avg, 2),
        "min": round(min_val, 2),
        "status": status,
        "count": len(values),
        "worst3": sorted(values)[:3]
    }


# ---------------- UI ----------------
HTML = """
<h2>BETON PDF ANALİZ (OCR)</h2>

<form method="post" enctype="multipart/form-data">
    PDF:
    <input type="file" name="file">
    <button type="submit">Analiz Et</button>
</form>

{% if r %}

    {% if r.error %}
        <p style="color:red">{{r.error}}</p>
    {% else %}

        Fck: {{r.fck}} <br>
        Numune: {{r.count}} <br>
        Ortalama: {{r.avg}} <br>
        Minimum: {{r.min}} <br>
        Durum: {{r.status}} <br>

        <h4>En düşük 3</h4>
        {{r.worst3}}

    {% endif %}

{% endif %}
"""


@app.route("/", methods=["GET", "POST"])
def home():
    result = None

    if request.method == "POST":
        file = request.files.get("file")

        fck, _, values = parse_pdf(file)
        result = analyze(fck, values)

    return render_template_string(HTML, r=result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
