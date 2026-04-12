from flask import Flask, request, render_template_string
import pdfplumber
import numpy as np
import re

app = Flask(__name__)


# ---------------- PDF TABLO OKUMA ----------------
def parse_pdf(file):

    text_rows = []

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:

            table = page.extract_table()

            if table:
                for row in table:
                    if row:
                        clean_row = [str(x).strip() if x else "" for x in row]
                        text_rows.append(clean_row)

    if not text_rows:
        return None, {}, []

    # ---------------- BETON SINIFI ----------------
    full_text = " ".join([" ".join(r) for r in text_rows])

    match = re.search(r"C(\d{2})/(\d{2})", full_text)

    fck = int(match.group(2)) if match else None


    # ---------------- 28 GÜN SÜTUNU BUL ----------------
    # (varsayım: "28" geçen kolon hedef kolon)
    values = []
    mixers = {}

    for row in text_rows:

        if len(row) < 3:
            continue

        # mikser numarası
        m = re.search(r"\d+", row[0])
        mixer_id = m.group() if m else None

        for cell in row:

            if not cell:
                continue

            if "28" in cell or re.match(r"^\d+(\.\d+)?$", cell):

                try:
                    v = float(cell.replace(",", "."))
                    if 10 < v < 120:

                        values.append(v)

                        if mixer_id:
                            mixers.setdefault(mixer_id, []).append(v)

                except:
                    pass

    return fck, mixers, values


# ---------------- ANALİZ ----------------
def analyze(fck, values, mixers):

    if not values or not fck:
        return {"error": "PDF kolonları doğru okunamadı"}

    avg = np.mean(values)
    min_val = min(values)

    n = len(values)

    # TS mantığı
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
<h2>BETON ANALİZ (PRO TABLO)</h2>

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
