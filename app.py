from flask import Flask, request, render_template_string
import pdfplumber
import numpy as np
import re

app = Flask(__name__)


# ---------------- PDF TABLO ANALİZ ----------------
def parse_pdf(file):

    table_data = []

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()

            if table:
                for row in table:
                    if row:
                        table_data.append(row)

    if not table_data:
        return None, {}

    # ---------------- HEADER BUL ----------------
    header = None
    for row in table_data:
        if any("28" in str(x) for x in row):
            header = row
            break

    if not header:
        return None, {}

    # kolon indexleri
    try:
        mixer_idx = next(i for i, x in enumerate(header) if "mikser" in str(x).lower())
        value_idx = next(i for i, x in enumerate(header) if "28" in str(x))
    except:
        return None, {}

    mixers = {}

    for row in table_data:

        if len(row) <= max(mixer_idx, value_idx):
            continue

        try:
            mixer = str(row[mixer_idx]).strip()
            value = str(row[value_idx]).replace(",", ".")

            if not mixer or mixer.lower() == "none":
                continue

            v = float(value)

            if 10 < v < 120:
                mixers.setdefault(mixer, []).append(v)

        except:
            continue

    all_values = [v for vals in mixers.values() for v in vals]

    # fck bul
    text = " ".join([" ".join(map(str, r)) for r in table_data])
    match = re.search(r"C(\d{2})/(\d{2})", text)

    fck = int(match.group(2)) if match else None

    return fck, mixers, all_values


# ---------------- ANALİZ ----------------
def analyze(fck, values, mixers):

    if not values or not fck:
        return {"error": "Tablo doğru okunamadı"}

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

    mixer_results = []
    bad = []

    for m, vals in mixers.items():

        if not vals:
            continue

        m_avg = np.mean(vals)
        diff = max(vals) - min(vals)

        if diff > 0.15 * m_avg or m_avg < (fck - 4):
            bad.append(m)

        mixer_results.append({
            "mixer": m,
            "avg": round(m_avg, 2),
            "diff": round(diff, 2)
        })

    return {
        "fck": fck,
        "avg": round(avg, 2),
        "min": round(min_val, 2),
        "status": status,
        "count": len(values),
        "mixers": mixer_results,
        "bad": bad,
        "worst3": sorted(values)[:3]
    }


# ---------------- UI ----------------
HTML = """
<h2>BETON ANALİZ (TABLO DOĞRU VERSİYON)</h2>

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

        <h4>Mikserler</h4>
        {% for m in r.mixers %}
            Mikser {{m.mixer}} → {{m.avg}} ({{m.diff}}) <br>
        {% endfor %}

        <h4>Problemli Mikserler</h4>
        {{r.bad}}

    {% endif %}

{% endif %}
"""


@app.route("/", methods=["GET", "POST"])
def home():
    result = None

    if request.method == "POST":
        file = request.files.get("file")
        fck, mixers, values = parse_pdf(file)
        result = analyze(fck, values, mixers)

    return render_template_string(HTML, r=result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
