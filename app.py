from flask import Flask, request, render_template_string
import pdfplumber
import numpy as np

app = Flask(__name__)


# ---------------- PDF OKUMA (SABİT KOLON) ----------------
def parse_pdf(file):

    rows = []

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()

            if table:
                for r in table:
                    if r and any(r):
                        rows.append(r)

    if not rows:
        return None, {}, []

    # ---------------- HEADER BUL ----------------
    header = None
    for r in rows:
        if r and any("28" in str(x) for x in r):
            header = r
            break

    if not header:
        return None, {}, []

    # ---------------- KOLON İNDEXLERİ ----------------
    try:
        mixer_idx = next(i for i, x in enumerate(header) if "mikser" in str(x).lower())
        value_idx = next(i for i, x in enumerate(header) if "28" in str(x))
    except:
        return None, {}, []

    mixers = {}

    for r in rows:

        if len(r) <= max(mixer_idx, value_idx):
            continue

        try:
            mixer = str(r[mixer_idx]).strip()
            value = str(r[value_idx]).replace(",", ".")

            if not mixer or mixer.lower() == "none":
                continue

            v = float(value)

            if 10 < v < 120:
                mixers.setdefault(mixer, []).append(v)

        except:
            continue

    values = [v for arr in mixers.values() for v in arr]

    # fck bul (C25/30 → 30)
    import re
    text = " ".join([" ".join(map(str, r)) for r in rows])
    match = re.search(r"C(\d{2})/(\d{2})", text)

    fck = int(match.group(2)) if match else None

    return fck, mixers, values


# ---------------- ANALİZ ----------------
def analyze(fck, values, mixers):

    if not values or not fck:
        return {"error": "PDF veri okunamadı"}

    avg = np.mean(values)
    min_val = min(values)
    n = len(values)

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
    bad = []

    for m, vals in mixers.items():

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
<h2>BETON ANALİZ SİSTEMİ (FINAL STABLE)</h2>

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
