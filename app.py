from flask import Flask, request, render_template_string
import pdfplumber
import numpy as np
import re

app = Flask(__name__)

# ---------------- SAFE PDF PARSER ----------------
def parse_pdf(file):
    text = ""

    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t
    except Exception as e:
        return [], {}

    # tüm sayıları çek
    raw_numbers = re.findall(r"\d+\.\d+|\d+", text)

    values = []
    for n in raw_numbers:
        try:
            v = float(n)
            if 5 < v < 100:   # beton mantığı filtre
                values.append(v)
        except:
            continue

    return values, {}


# ---------------- ANALİZ MOTORU ----------------
def analyze(fck, values):
    if len(values) == 0:
        return {"error": "PDF'den veri okunamadı"}

    avg = round(np.mean(values), 2)
    min_val = round(min(values), 2)

    n = len(values)

    if n == 1:
        limit = fck
    elif 2 <= n <= 4:
        limit = fck + 1
    else:
        limit = fck + 2

    status = "UYGUN"
    if avg < limit or min_val < fck - 4:
        status = "UYGUN DEĞİL"

    worst3 = sorted(values)[:3]

    return {
        "avg": avg,
        "min": min_val,
        "status": status,
        "worst3": worst3,
        "count": len(values)
    }


# ---------------- UI ----------------
HTML = """
<h2>PDF Beton Analiz Sistemi</h2>

<form method="post" enctype="multipart/form-data">
    Beton Sınıfı (fck):
    <select name="fck">
        <option value="30">C25/30</option>
        <option value="35">C30/37</option>
        <option value="40">C35/45</option>
    </select><br><br>

    PDF:
    <input type="file" name="file"><br><br>

    <button type="submit">Analiz Et</button>
</form>

{% if result %}
    <h3>SONUÇ</h3>

    {% if result.error %}
        <p style="color:red">{{result.error}}</p>
    {% else %}
        Ortalama: {{result.avg}} <br>
        Minimum: {{result.min}} <br>
        Durum: {{result.status}} <br>
        Numune sayısı: {{result.count}} <br>

        <h4>En düşük 3 değer</h4>
        {{result.worst3}}
    {% endif %}
{% endif %}
"""


@app.route("/", methods=["GET", "POST"])
def home():
    result = None

    if request.method == "POST":
        fck = float(request.form["fck"])
        file = request.files["file"]

        values, _ = parse_pdf(file)
        result = analyze(fck, values)

    return render_template_string(HTML, result=result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
