from flask import Flask, request, render_template_string
import pdfplumber
import numpy as np
import re

app = Flask(__name__)


# ---------------- PDF PARSE ----------------
def parse_pdf(file):

    mixers = {}

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:

            table = page.extract_table()

            if not table:
                continue

            for row in table:

                if not row or len(row) < 10:
                    continue

                try:
                    # 🔥 SABİT KOLONLAR
                    mixer = str(row[1]).strip()

                    # 28 GÜNLÜK NUMUNE (tek tek değerler)
                    val_raw = str(row[-2]).replace(",", ".").strip()

                    if val_raw == "" or val_raw.lower() == "none":
                        continue

                    value = float(val_raw)

                    if 10 < value < 100:
                        mixers.setdefault(mixer, []).append(value)

                except:
                    continue

    values = [v for arr in mixers.values() for v in arr]

    # FCK (C25/30 → 30)
    text = ""
    with pdfplumber.open(file) as pdf:
        for p in pdf.pages:
            t = p.extract_text()
            if t:
                text += t

    match = re.search(r"C(\d{2})/(\d{2})", text)
    fck = int(match.group(2)) if match else 30

    return fck, mixers, values


# ---------------- ANALİZ ----------------
def analyze(fck, mixers, values):

    if not values:
        return {"error": "Veri okunamadı"}

    n = len(values)
    avg = np.mean(values)
    min_val = min(values)

    # TS limit
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
    bad_mixers = []

    for m, vals in mixers.items():

        if len(vals) == 0:
            continue

        m_avg = np.mean(vals)
        diff = max(vals) - min(vals)

        dist_ok = diff <= (0.15 * m_avg)
        strength_ok = m_avg >= (fck - 4)

        m_status = "OK"
        if not dist_ok or not strength_ok:
            m_status = "PROBLEM"
            bad_mixers.append(m)

        mixer_results.append({
            "mixer": m,
            "count": len(vals),
            "avg": round(m_avg, 2),
            "diff": round(diff, 2),
            "status": m_status
        })

    return {
        "fck": fck,
        "numune": n,
        "ortalama": round(avg, 2),
        "min": round(min_val, 2),
        "status": status,
        "mixers": mixer_results,
        "bad_mixers": bad_mixers,
        "worst3": sorted(values)[:3]
    }


# ---------------- UI ----------------
HTML = """
<h2>BETON ANALİZ SİSTEMİ</h2>

<form method="post" enctype="multipart/form-data">
    PDF yükle:
    <input type="file" name="file">
    <button type="submit">Analiz Et</button>
</form>

{% if r %}

    {% if r.error %}
        <p style="color:red">{{r.error}}</p>
    {% else %}

        <h3>GENEL</h3>
        Fck: {{r.fck}} <br>
        Numune: {{r.numune}} <br>
        Ortalama: {{r.ortalama}} <br>
        Minimum: {{r.min}} <br>
        Durum: {{r.status}} <br>

        <h3>MİKSER ANALİZİ</h3>
        {% for m in r.mixers %}
            Mikser {{m.mixer}} →
            Adet: {{m.count}} |
            Ort: {{m.avg}} |
            Fark: {{m.diff}} |
            {{m.status}} <br>
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

        fck, mixers, values = parse_pdf(file)
        result = analyze(fck, mixers, values)

    return render_template_string(HTML, r=result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
