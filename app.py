from flask import Flask, request, render_template_string
import pdfplumber
import numpy as np

app = Flask(__name__)

GLOBAL_STATE = {
    "header": None,
    "rows": None,
    "mixer_idx": None,
    "value_idx": None
}


# ---------------- PDF OKU ----------------
def read_pdf(file):

    rows = []

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                rows.extend(table)

    if not rows:
        return None

    return rows


# ---------------- KOLON BUL ----------------
def detect_columns(rows):

    header = rows[0]

    cols = {
        "columns": header,
        "suggest_mixer": None,
        "suggest_value": None
    }

    for i, c in enumerate(header):

        c_str = str(c).lower()

        if "mikser" in c_str or "mixer" in c_str:
            cols["suggest_mixer"] = i

        if "28" in c_str:
            cols["suggest_value"] = i

    return cols


# ---------------- ANALİZ ----------------
def analyze(rows, mixer_idx, value_idx, fck=30):

    mixers = {}

    for r in rows[1:]:

        if len(r) <= max(mixer_idx, value_idx):
            continue

        try:
            mixer = str(r[mixer_idx]).strip()
            value = float(str(r[value_idx]).replace(",", "."))

            mixers.setdefault(mixer, []).append(value)

        except:
            continue

    all_values = [v for arr in mixers.values() for v in arr]

    if not all_values:
        return {"error": "Veri yok"}

    avg = np.mean(all_values)
    min_val = min(all_values)

    status = "UYGUN"
    if avg < fck + 2 or min_val < fck - 4:
        status = "UYGUN DEĞİL"

    return {
        "avg": round(avg,2),
        "min": round(min_val,2),
        "status": status,
        "count": len(all_values),
        "mixers": mixers
    }


# ---------------- UI ----------------
HTML = """
<h2>BETON ANALİZ - KOLON SEÇİMLİ SİSTEM</h2>

<form method="post" enctype="multipart/form-data">
    PDF:
    <input type="file" name="file">
    <button type="submit">PDF Yükle</button>
</form>

{% if step == 1 %}

    <h3>Kolonları Seç</h3>

    <form method="post">
        <input type="hidden" name="step" value="2">

        <p>Mikser Kolonu:</p>
        <select name="mixer">
            {% for i,c in cols.columns %}
                <option value="{{i}}">{{c}}</option>
            {% endfor %}
        </select>

        <p>28 Gün Kolonu:</p>
        <select name="value">
            {% for i,c in cols.columns %}
                <option value="{{i}}">{{c}}</option>
            {% endfor %}
        </select>

        <button type="submit">Kaydet & Analiz Et</button>
    </form>

{% endif %}


{% if step == 2 %}

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

        step = request.form.get("step")

        # 1. PDF yükleme
        if not step:

            file = request.files.get("file")
            rows = read_pdf(file)

            if not rows:
                return "PDF okunamadı"

            cols = detect_columns(rows)

            GLOBAL_STATE["rows"] = rows

            return render_template_string(HTML, step=1, cols=cols)

        # 2. analiz
        else:

            mixer_idx = int(request.form.get("mixer"))
            value_idx = int(request.form.get("value"))

            rows = GLOBAL_STATE["rows"]

            result = analyze(rows, mixer_idx, value_idx)

            return render_template_string(HTML, step=2, r=result)

    return render_template_string(HTML, step=0)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
