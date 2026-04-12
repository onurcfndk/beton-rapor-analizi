from flask import Flask, request, render_template_string
import pdfplumber
import re
import numpy as np

app = Flask(__name__)

# -----------------------------
# TS ANALİZ MOTORU
# -----------------------------
def analyze(fck, values, mixer_data):
    n = len(values)
    avg = round(np.mean(values), 2)
    min_val = round(min(values), 2)

    if n == 1:
        limit = fck
    elif 2 <= n <= 4:
        limit = fck + 1
    else:
        limit = fck + 2

    status = "UYGUN"
    if avg < limit or min_val < fck - 4:
        status = "UYGUN DEĞİL"

    mixers = []
    bad_mixers = []

    for m_no, vals in mixer_data.items():
        m_avg = round(np.mean(vals), 2)
        diff = round(max(vals) - min(vals), 2)

        limit_diff = 0.15 * m_avg

        dist = "UYGUN" if diff <= limit_diff else "HATALI"
        strength = "YETERLİ" if m_avg >= (fck - 4) else "DÜŞÜK"

        m_status = "OK"
        if dist == "HATALI" or strength == "DÜŞÜK":
            m_status = "PROBLEM"
            bad_mixers.append(m_no)
            status = "UYGUN DEĞİL"

        mixers.append({
            "no": m_no,
            "avg": m_avg,
            "diff": diff,
            "dist": dist,
            "strength": strength,
            "status": m_status
        })

    worst = sorted(values)[:3]

    return {
        "avg": avg,
        "min": min_val,
        "status": status,
        "mixers": mixers,
        "bad_mixers": bad_mixers,
        "worst": worst
    }


# -----------------------------
# PDF PARSER (GERÇEK KISIM)
# -----------------------------
def parse_pdf(file):
    text = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""

    # Mikser bazlı ayırma (örnek pattern)
    mixers = {}

    lines = text.split("\n")

    current_mixer = None

    for line in lines:

        # Mikser yakala
        m = re.search(r"Mikser\s*(\d+)", line)
        if m:
            current_mixer = m.group(1)
            if current_mixer not in mixers:
                mixers[current_mixer] = []
            continue

        # Sayıları yakala (28 günlük sonuçlar)
        numbers = re.findall(r"\d+\.\d+|\d+", line)

        if current_mixer and numbers:
            for n in numbers:
                val = float(n)

                # sadece 10-80 arası beton mantıklı değerleri al
                if 10 < val < 80:
                    mixers[current_mixer].append(val)

    # tüm değerleri düz liste
    all_values = [v for vals in mixers.values() for v in vals]

    return mixers, all_values


# -----------------------------
# UI
# -----------------------------
HTML = """
<h2>PDF Beton Analiz Sistemi</h2>

<form method="post" enctype="multipart/form-data">
    Beton Sınıfı:
    <select name="class">
        <option value="30">C25/30</option>
        <option value="35">C30/35</option>
        <option value="40">C35/40</option>
    </select><br><br>

    PDF:
    <input type="file" name="file"><br><br>

    <button type="submit">Analiz Et</button>
</form>

{% if result %}
    <h3>SONUÇ</h3>
    Ortalama: {{result['avg']}} <br>
    Minimum: {{result['min']}} <br>
    Durum: {{result['status']}} <br>

    <h4>Problemli Mikserler:</h4>
    {{result['bad_mixers']}}
{% endif %}
"""


@app.route("/", methods=["GET", "POST"])
def home():
    result = None

    if request.method == "POST":
        fck = float(request.form["class"])
        file = request.files["file"]

        mixers, values = parse_pdf(file)

        result = analyze(fck, values, mixers)

    return render_template_string(HTML, result=result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
