from flask import Flask, request, render_template_string
import pdfplumber
import numpy as np
import re

app = Flask(__name__)

# ---------------- PDF PARSER ----------------
def parse_pdf(file):
    text = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t

    # Beton sınıfı bul
    match = re.search(r"C(\d{2})/(\d{2})", text)

    fck = None
    if match:
        cube = int(match.group(2))
        cyl = int(match.group(1))

        # varsayılan: küp kullan (senin kuralın)
        fck = cube

    # Mikserleri bul
    mixers = {}
    current = None

    lines = text.split("\n")

    for line in lines:

        m = re.search(r"Mikser\s*(\d+)", line)
        if m:
            current = m.group(1)
            if current not in mixers:
                mixers[current] = []
            continue

        nums = re.findall(r"\d+\.\d+|\d+", line)

        if current and nums:
            for n in nums:
                try:
                    v = float(n)
                    if 5 < v < 100:
                        mixers[current].append(v)
                except:
                    pass

    all_values = [v for vals in mixers.values() for v in vals]

    return fck, mixers, all_values


# ---------------- ANALİZ MOTORU ----------------
def analyze(fck, values, mixers):

    avg = round(np.mean(values), 2)
    min_val = round(min(values), 2)

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
        m_avg = round(np.mean(vals), 2)
        diff = round(max(vals) - min(vals), 2)

        limit_diff = 0.15 * m_avg

        dist = "UYGUN" if diff <= limit_diff else "HATALI"
        strength = "YETERLİ" if m_avg >= (fck - 4) else "DÜŞÜK"

        m_status = "OK"
        if dist == "HATALI" or strength == "DÜŞÜK":
            m_status = "PROBLEM"
            bad.append(m)

        mixer_results.append({
            "mixer": m,
            "avg": m_avg,
            "diff": diff,
            "dist": dist,
            "strength": strength,
            "status": m_status
        })

    worst3 = sorted(values)[:3]

    return {
        "fck": fck,
        "avg": avg,
        "min": min_val,
        "status": status,
        "mixers": mixer_results,
        "bad_mixers": bad,
        "worst3": worst3
    }


# ---------------- UI ----------------
HTML = """
<h2>Beton PDF Analiz Sistemi</h2>

<form method="post" enctype="multipart/form-data">
    PDF:
    <input type="file" name="file">
    <button type="submit">Analiz Et</button>
</form>

{% if r %}
    <h3>SONUÇ</h3>

    {% if r.fck %}
        Fck: {{r.fck}} <br>
    {% else %}
        Fck bulunamadı <br>
    {% endif %}

    Ortalama: {{r.avg}} <br>
    Minimum: {{r.min}} <br>
    Durum: {{r.status}} <br>

    <h4>En düşük 3</h4>
    {{r.worst3}}

    <h4>Mikserler</h4>
    {% for m in r.mixers %}
        Mikser {{m.mixer}} → {{m.status}} ({{m.avg}})
        <br>
    {% endfor %}
{% endif %}
"""


@app.route("/", methods=["GET", "POST"])
def home():
    result = None

    if request.method == "POST":
        file = request.files["file"]

        fck, mixers, values = parse_pdf(file)

        if fck is None:
            return render_template_string(HTML, r={"status": "FCK okunamadı"})

        result = analyze(fck, values, mixers)

    return render_template_string(HTML, r=result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
