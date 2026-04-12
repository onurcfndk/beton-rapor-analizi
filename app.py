from flask import Flask, request, render_template_string
import pdfplumber
import numpy as np
import re

app = Flask(__name__)

# ---------------- PDF PARSER ----------------
def parse_pdf(file):
    text = ""

    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t
    except:
        return None, []

    if not text:
        return None, []

    # Beton sınıfı (C25/30 → küp = 30)
    match = re.search(r"C(\d{2})/(\d{2})", text)

    fck = None
    if match:
        try:
            fck = int(match.group(2))  # küp
        except:
            fck = None

    # Sayıları çek
    numbers = re.findall(r"\d+\.\d+|\d+", text)

    values = []
    for n in numbers:
        try:
            n = str(n).replace(",", ".")
            v = float(n)

            # beton aralığı filtresi
            if 10 < v < 120:
                values.append(v)
        except:
            continue

    return fck, values


# ---------------- ANALİZ ----------------
def analyze(fck, values):

    if not values:
        return {"error": "PDF'den sayısal veri çekilemedi"}

    if fck is None:
        return {"error": "Beton sınıfı okunamadı"}

    avg = round(np.mean(values), 2)
    min_val = round(min(values), 2)

    n = len(values)

    # TS mantığı
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
        "avg": avg,
        "min": min_val,
        "status": status,
        "worst3": sorted(values)[:3],
        "count": len(values)
    }


# ---------------- UI ----------------
HTML = """
<h2>PDF Beton Analiz Sistemi</h2>

<form method="post" enctype="multipart/form-data">
    PDF yükle:
    <input type="file" name="file">
    <button type="submit">Analiz Et</button>
</form>

{% if r %}
    {% if r.error %}
        <p style="color:red">{{r.error}}</p>
    {% else %}
        <h3>SONUÇ</h3>

        Fck: {{r.fck}} <br>
        Numune sayısı: {{r.count}} <br>
        Ortalama: {{r.avg}} <br>
        Minimum: {{r.min}} <br>
        Durum: {{r.status}} <br>

        <h4>En düşük 3 değer</h4>
        {{r.worst3}}
    {% endif %}
{% endif %}
"""


@app.route("/", methods=["GET", "POST"])
def home():
    result = None

    if request.method == "POST":
        file = request.files.get("file")

        if not file:
            return render_template_string(HTML, r={"error": "Dosya yüklenmedi"})

        fck, values = parse_pdf(file)
        result = analyze(fck, values)

    return render_template_string(HTML, r=result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
