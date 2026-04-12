from flask import Flask, request, render_template_string
import pdfplumber
import numpy as np
import re

app = Flask(__name__)

# ---------------- PDF PARSER (TABLE BASED) ----------------
def parse_pdf(file):
    text = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()

            if table:
                for row in table:
                    if row:
                        text += " ".join([str(x) for x in row if x])

    # Beton sınıfı
    match = re.search(r"C(\d{2})/(\d{2})", text)

    fck = None
    if match:
        fck = int(match.group(2))  # küp

    # Mikser bazlı ayırma
    mixers = {}

    current_mixer = None

    lines = text.split("\n")

    for line in lines:

        m = re.search(r"Mikser\s*(\d+)", line)
        if m:
            current_mixer = m.group(1)
            if current_mixer not in mixers:
                mixers[current_mixer] = []
            continue

        nums = re.findall(r"\d+\.\d+|\d+", line)

        if current_mixer:
            for n in nums:
                try:
                    v = float(n)
                    if 10 < v < 120:
                        mixers[current_mixer].append(v)
                except:
                    pass

    all_values = [v for vals in mixers.values() for v in vals]

    return fck, mixers, all_values


# ---------------- ENGINE ----------------
def analyze(fck, values, mixers):

    if not values or not fck:
        return {"error": "Veri okunamadı"}

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

        m_avg = np.mean(vals)
        m_min = min(vals)
        m_max = max(vals)

        diff = m_max - m_min

        dist_ok = diff <= (0.15 * m_avg)
        strength_ok = m_avg >= (fck - 4)

        if not dist_ok or not strength_ok:
            bad.append(m)

        mixer_results.append({
            "mixer": m,
            "avg": round(m_avg, 2),
            "diff": round(diff, 2),
            "dist": dist_ok,
            "strength": strength_ok
        })

    return {
        "fck": fck,
        "avg": round(avg, 2),
        "min": round(min_val, 2),
        "status": status,
        "mixers": mixer_results,
        "bad": bad,
        "count": len(values),
        "worst3": sorted(values)[:3]
    }


# ---------------- UI ----------------
HTML = """
<h2>BETON PDF ANALİZ (PRO)</h2>

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
            Mikser {{m.mixer}} → {{m.avg}} ({{m.diff}})
            <br>
        {% endfor %}

        <h4>Problemli Mikserler</h4>
        {{r.bad}}

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

        fck, mixers, values = parse_pdf(file)

        result = analyze(fck, values, mixers)

    return render_template_string(HTML, r=result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
