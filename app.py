from flask import Flask, request, render_template_string
import pdfplumber
import numpy as np
import re

app = Flask(__name__)


# ---------------- PDF TEXT PARSER ----------------
def parse_pdf(file):

    text = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += " " + t

    if not text:
        return None, [], {}

    # ---------------- FCK ----------------
    match = re.search(r"C\s*(\d{2})\s*/\s*(\d{2})", text)
    fck = int(match.group(2)) if match else None

    # ---------------- 28 GÜN DEĞERLERİ ----------------
    # 28 gün geçen sayıları yakala (yakın pattern)
    values = []

    pattern = re.findall(r"28\s*[^0-9]{0,10}(\d{2,3}[\.,]?\d*)", text)

    for p in pattern:
        try:
            v = float(p.replace(",", "."))
            values.append(v)
        except:
            pass

    # fallback: tüm sayılar (filtreli)
    if not values:
        nums = re.findall(r"\d+\.\d+|\d+", text)
        for n in nums:
            try:
                v = float(n)
                if 10 < v < 120:
                    values.append(v)
            except:
                pass

    # ---------------- MİKSER ----------------
    mixers = {}

    mixer_matches = re.findall(r"(?:Mikser|T\.?Mikser)\s*[:\-]?\s*(\d+)", text)

    for i, m in enumerate(mixer_matches):

        # aynı sıradaki 28 gün değerini bağla
        if i < len(values):
            mixers.setdefault(m, []).append(values[i])

    return fck, values, mixers


# ---------------- ANALİZ ----------------
def analyze(fck, values, mixers):

    if not values or not fck:
        return {"error": "PDF içinden veri çıkarılamadı (format farklı olabilir)"}

    n = len(values)
    avg = np.mean(values)
    min_val = min(values)

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

        ok = diff <= (0.15 * m_avg) and m_avg >= (fck - 4)

        if not ok:
            bad.append(m)

        mixer_results.append({
            "mixer": m,
            "avg": round(m_avg, 2),
            "diff": round(diff, 2),
            "status": "OK" if ok else "PROBLEM"
        })

    return {
        "fck": fck,
        "numune": n,
        "avg": round(avg, 2),
        "min": round(min_val, 2),
        "status": status,
        "mixers": mixer_results,
        "bad": bad,
        "worst3": sorted(values)[:3]
    }


# ---------------- UI ----------------
HTML = """
<h2>BETON ANALİZ (TEXT MODE FINAL)</h2>

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
        Numune: {{r.numune}} <br>
        Ortalama: {{r.avg}} <br>
        Minimum: {{r.min}} <br>
        Durum: {{r.status}} <br>

        <h4>Mikserler</h4>
        {% for m in r.mixers %}
            Mikser {{m.mixer}} → {{m.avg}} | {{m.status}} <br>
        {% endfor %}

        <h4>Problemli</h4>
        {{r.bad}}

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
