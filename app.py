from flask import Flask, request, render_template_string
import pdfplumber
import numpy as np
import re

app = Flask(__name__)


# ---------------- SMART COLUMN FINDER ----------------
def find_column(rows, keyword_list):

    for r in rows[:5]:  # sadece üst kısım

        for i, cell in enumerate(r):

            cell_str = str(cell).lower()

            for kw in keyword_list:
                if kw in cell_str:
                    return i

    return None


# ---------------- PDF PARSE ----------------
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

    if not rows:
        return None, [], {}

    # ---------------- FCK ----------------
    match = re.search(r"C\s*(\d{2})\s*/\s*(\d{2})", full_text)
    fck = int(match.group(2)) if match else None

    # ---------------- COLUMN DETECTION ----------------
    mixer_idx = find_column(rows, ["mikser", "mixer", "t.mikser"])
    value_idx = find_column(rows, ["28", "28 gün", "28gun", "28-day"])

    if mixer_idx is None:
        mixer_idx = 0

    if value_idx is None:
        value_idx = -1

    mixers = {}

    # ---------------- ROW PARSE ----------------
    for r in rows:

        if len(r) <= max(mixer_idx, value_idx):
            continue

        try:
            mixer_raw = str(r[mixer_idx]).strip()
            value_raw = str(r[value_idx]).replace(",", ".")

            mixer = re.findall(r"\d+", mixer_raw)
            mixer = mixer[0] if mixer else mixer_raw

            value = float(value_raw)

            if 10 < value < 120:

                mixers.setdefault(mixer, []).append(value)

        except:
            continue

    values = [v for arr in mixers.values() for v in arr]

    return fck, values, mixers


# ---------------- ANALYSIS ----------------
def analyze(fck, values, mixers):

    if not values:
        return {"error": "Hiç veri çekilemedi (PDF format kontrol)"}

    if not fck:
        return {"error": "Fck bulunamadı"}

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


HTML = """
<h2>BETON ANALİZ (SMART PARSER v2)</h2>

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
            {{m.mixer}} → {{m.avg}} | {{m.diff}} | {{m.status}} <br>
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
