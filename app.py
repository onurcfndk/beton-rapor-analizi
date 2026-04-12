from flask import Flask, request, render_template_string
import pdfplumber
import numpy as np
import re

app = Flask(__name__)


# ---------------- PDF OKU ----------------
def parse_pdf(file):

    rows = []
    full_text = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:

            table = page.extract_table()
            if table:
                rows.extend(table)

            text = page.extract_text()
            if text:
                full_text += " " + text

    # ---------------- FCK ----------------
    match = re.search(r"C(\d{2})/(\d{2})", full_text)
    fck = int(match.group(2)) if match else None

    if not rows:
        return fck, [], {}

    # ---------------- HEADER ----------------
    header = rows[0]

    try:
        mixer_idx = next(i for i, x in enumerate(header) if "mikser" in str(x).lower())
        day28_idx = next(i for i, x in enumerate(header) if "28" in str(x))
    except:
        return fck, [], {}

    mixers = {}

    for r in rows[1:]:

        if len(r) <= max(mixer_idx, day28_idx):
            continue

        try:
            mixer = str(r[mixer_idx]).strip()
            value = float(str(r[day28_idx]).replace(",", "."))

            if mixer and 10 < value < 120:
                mixers.setdefault(mixer, []).append(value)

        except:
            continue

    all_values = [v for arr in mixers.values() for v in arr]

    return fck, all_values, mixers


# ---------------- ANALİZ ----------------
def analyze(fck, values, mixers):

    if not values or not fck:
        return {"error": "Veri eksik"}

    n = len(values)
    avg = np.mean(values)
    min_val = min(values)

    # ---------------- GLOBAL KONTROL ----------------
    if n == 1:
        limit = fck
    elif n <= 4:
        limit = fck + 1
    else:
        limit = fck + 2

    global_status = "UYGUN"
    if avg < limit or min_val < fck - 4:
        global_status = "UYGUN DEĞİL"

    # ---------------- MİKSER KONTROL ----------------
    mixer_results = []
    bad_mixers = []

    for m, vals in mixers.items():

        m_avg = np.mean(vals)
        diff = max(vals) - min(vals)

        dist_ok = diff <= (0.15 * m_avg)
        strength_ok = m_avg >= (fck - 4)

        status = "OK"
        if not dist_ok or not strength_ok:
            status = "PROBLEM"
            bad_mixers.append(m)

        mixer_results.append({
            "mixer": m,
            "avg": round(m_avg, 2),
            "diff": round(diff, 2),
            "status": status
        })

    # ---------------- SONUÇ ----------------
    return {
        "fck": fck,
        "numune": n,
        "ortalama": round(avg, 2),
        "min": round(min_val, 2),
        "global_status": global_status,
        "mixers": mixer_results,
        "bad_mixers": bad_mixers,
        "worst3": sorted(values)[:3]
    }


# ---------------- UI ----------------
HTML = """
<h2>BETON ANALİZ SİSTEMİ (FINAL LOGIC)</h2>

<form method="post" enctype="multipart/form-data">
    PDF:
    <input type="file" name="file">
    <button type="submit">Analiz Et</button>
</form>

{% if r %}

    {% if r.error %}
        <p style="color:red">{{r.error}}</p>
    {% else %}

        <h3>GLOBAL</h3>
        Fck: {{r.fck}} <br>
        Numune: {{r.numune}} <br>
        Ortalama: {{r.ortalama}} <br>
        Minimum: {{r.min}} <br>
        Durum: {{r.global_status}} <br>

        <h3>MİKSERLER</h3>
        {% for m in r.mixers %}
            {{m.mixer}} → {{m.avg}} | {{m.diff}} | {{m.status}} <br>
        {% endfor %}

        <h3>Problemli Mikserler</h3>
        {{r.bad_mixers}}

    {% endif %}

{% endif %}
"""


@app.route("/", methods=["GET", "POST"])
def home():
    result = None

    if request.method == "POST":
        file = request.files.get("file")
        fck, values, mixers = parse_pdf(file)
        result = analyze(fck, values, mixers)

    return render_template_string(HTML, r=result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
