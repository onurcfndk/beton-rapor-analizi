from flask import Flask, request, render_template_string
import pdfplumber
import numpy as np
import re

app = Flask(__name__)

# ---------------- PDF PARSER (ROBUST) ----------------
def parse_pdf(file):
    text = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:

            # 1) tablo dene
            table = page.extract_table()
            if table:
                for row in table:
                    if row:
                        text += " ".join([str(x) for x in row if x])

            # 2) text dene (KRİTİK FIX)
            page_text = page.extract_text()
            if page_text:
                text += " " + page_text

    text = text.strip()

    if not text:
        return None, {}, []

    # ---------------- BETON SINIFI ----------------
    match = re.search(r"C(\d{2})/(\d{2})", text)

    fck = None
    if match:
        fck = int(match.group(2))  # küp

    # ---------------- MİKSERLER ----------------
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

        if current:
            for n in nums:
                try:
                    v = float(n.replace(",", "."))
                    if 10 < v < 120:
                        mixers[current].append(v)
                except:
                    pass

    values = [v for vals in mixers.values() for v in vals]

    return fck, mixers, values


# ---------------- ANALİZ ----------------
def analyze(fck, values, mixers):

    if not values:
        return {"error": "PDF'den hiç sayısal veri çekilemedi"}

    if not fck:
        return {"error": "Beton sınıfı bulunamadı"}

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
<h2>BETON PDF ANALİZ</h2>

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
