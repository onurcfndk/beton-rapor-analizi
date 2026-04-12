from flask import Flask, request, render_template_string
import pdfplumber
import numpy as np

app = Flask(__name__)


# ---------------- PDF OKU ----------------
def read_pdf(file):
    rows = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            t = page.extract_table()
            if t:
                rows.extend(t)

    return rows if rows else None


# ---------------- ANALİZ ----------------
def analyze(rows, mixer_idx, value_idx):

    mixers = {}

    for r in rows[1:]:

        try:
            mixer = str(r[mixer_idx]).strip()
            value = float(str(r[value_idx]).replace(",", "."))

            mixers.setdefault(mixer, []).append(value)

        except:
            continue

    values = [v for arr in mixers.values() for v in arr]

    if not values:
        return {"error": "Veri yok"}

    avg = np.mean(values)
    min_val = min(values)

    status = "UYGUN"

    if avg < 30 or min_val < 26:
        status = "UYGUN DEĞİL"

    return {
        "avg": round(avg,2),
        "min": round(min_val,2),
        "status": status,
        "count": len(values),
        "mixers": mixers
    }


# ---------------- UI ----------------
HTML = """
<h2>BETON ANALİZ (STABLE FIX)</h2>

{% if step == 0 %}

<form method="post" enctype="multipart/form-data">
    <input type="file" name="file">
    <button type="submit">PDF Yükle</button>
</form>

{% endif %}


{% if step == 1 %}

<form method="post">

    <input type="hidden" name="rows" value="{{rows}}">

    <p>Mikser kolonu index:</p>
    <input name="mixer">

    <p>28 Gün kolonu index:</p>
    <input name="value">

    <button type="submit">Analiz Et</button>
</form>

{% endif %}


{% if r %}

<h3>SONUÇ</h3>

Ortalama: {{r.avg}} <br>
Minimum: {{r.min}} <br>
Durum: {{r.status}} <br>
Numune: {{r.count}} <br>

{% endif %}
"""


@app.route("/", methods=["GET", "POST"])
def home():

    if request.method == "POST":

        file = request.files.get("file")

        if file:
            rows = read_pdf(file)

            if not rows:
                return "PDF okunamadı"

            return render_template_string(HTML, step=1, rows=len(rows))

        mixer_idx = int(request.form.get("mixer"))
        value_idx = int(request.form.get("value"))

        # burada basit demo (state yok)
        return render_template_string(HTML, step=2, r={
            "avg": 0,
            "min": 0,
            "status": "TEST",
            "count": 0
        })

    return render_template_string(HTML, step=0)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
