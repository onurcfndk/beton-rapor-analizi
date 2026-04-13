from flask import Flask, request, render_template_string
import pdfplumber
import numpy as np
import re

app = Flask(__name__)

# ---------------- PDF OKUMA ----------------
def parse_pdf(file):

    mixers = {}
    text = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:

            t = page.extract_text()
            if t:
                text += t

            table = page.extract_table()
            if not table:
                continue

            header = table[0]

            col_index = None

            # 🔥 ESNEK BAŞLIK BULMA
            for i, h in enumerate(header):
                h_str = str(h).lower()

                if "28" in h_str and "gün" in h_str:
                    col_index = i
                    break

            if col_index is None:
                continue

            for row in table[1:]:

                if not row or len(row) <= col_index:
                    continue

                try:
                    mixer_raw = str(row[1]).strip()

                    if not mixer_raw.isdigit():
                        continue

                    mixer = mixer_raw

                    val_raw = str(row[col_index]).replace(",", ".").replace("*", "").strip()

                    if val_raw == "" or val_raw.lower() == "none":
                        continue

                    # ❗ ortalama gibi uzun değerleri ele
                    if len(val_raw) > 5:
                        continue

                    value = float(val_raw)

                    # ❗ ekstra filtre (çok önemli)
                    if 30 < value < 70:
                        mixers.setdefault(mixer, []).append(value)

                except:
                    continue

    # ---------------- FCK ----------------
    match = re.search(r"C(\d{2})/(\d{2})", text)

    if match:
        if "silindir" in text.lower():
            shape = "Silindir"
            fck = int(match.group(1))
        else:
            shape = "Küp"
            fck = int(match.group(2))
    else:
        shape = "Bilinmiyor"
        fck = 30

    values = [v for arr in mixers.values() for v in arr]

    return fck, mixers, values, shape


# ---------------- ANALİZ ----------------
def analyze(fck, mixers, values, shape):

    if not values:
        return {"error": "PDF veri okunamadı"}

    avg = np.mean(values)
    min_val = min(values)

    mixer_count = len(mixers)

    if mixer_count == 1:
        limit = fck
    elif 2 <= mixer_count <= 4:
        limit = fck + 1
    else:
        limit = fck + 2

    status = "UYGUN" if (avg >= limit and min_val >= (fck - 4)) else "UYGUN DEĞİL"

    mixer_results = []
    bad_mixers = []

    for m, vals in mixers.items():

        if len(vals) < 2:
            continue

        m_avg = np.mean(vals)
        diff = max(vals) - min(vals)
        limit_diff = 0.15 * m_avg

        dist_ok = diff <= limit_diff
        strength_ok = m_avg >= (fck - 4)

        explanations = []

        explanations.append("✔ Dağılım uygun" if dist_ok else "❌ Dağılım fazla")
        explanations.append(
            f"✔ Dayanım ≥ {fck-4}" if strength_ok
            else f"❌ Dayanım < {fck-4}"
        )

        m_status = "OK" if (dist_ok and strength_ok) else "PROBLEM"

        if m_status == "PROBLEM":
            bad_mixers.append(m)

        mixer_results.append({
            "mixer": m,
            "vals": [round(v,1) for v in vals],
            "count": len(vals),
            "avg": round(m_avg, 2),
            "diff": round(diff, 2),
            "limit": round(limit_diff, 2),
            "status": m_status,
            "explanations": explanations
        })

    return {
        "shape": shape,
        "fck": fck,
        "numune": len(values),
        "ortalama": round(avg, 2),
        "min": round(min_val, 2),
        "limit": limit,
        "status": status,
        "mixers": mixer_results,
        "bad_mixers": bad_mixers
    }


# ---------------- UI ----------------
HTML = """
<style>
body {
    font-family: Arial;
    background: linear-gradient(135deg, #dfe9f3, #ffffff);
    padding: 30px;
}

.container {
    max-width: 900px;
    margin: auto;
}

.header {
    background: #1e3a8a;
    color: white;
    padding: 20px;
    border-radius: 12px;
    text-align: center;
}

.card {
    background: white;
    padding: 20px;
    margin-top: 20px;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.ok { color: #16a34a; font-weight: bold; }
.bad { color: #dc2626; font-weight: bold; }

.upload-box {
    margin-top:20px;
    padding:20px;
    background:#f1f5f9;
    border-radius:12px;
    text-align:center;
}

input[type=file] {
    margin-bottom:15px;
}

button {
    background:#2563eb;
    color:white;
    border:none;
    padding:12px 25px;
    border-radius:8px;
    font-size:16px;
    cursor:pointer;
}

button:hover {
    background:#1d4ed8;
}
</style>

<div class="container">

<div class="header">
<h2>BETON ANALİZ SİSTEMİ</h2>
</div>

<div class="upload-box">
<form method="post" enctype="multipart/form-data">
    <input type="file" name="file"><br>
    <button type="submit">📊 Analiz Et</button>
</form>
</div>

{% if r %}
    {% if r.error %}
        <p class="bad">{{r.error}}</p>
    {% else %}

    <div class="card">
    <h3>GENEL SONUÇ</h3>
    Numune Tipi: {{r.shape}} <br>
    Fck: {{r.fck}} <br>
    Numune: {{r.numune}} <br>
    Ortalama: {{r.ortalama}} <br>
    Minimum: {{r.min}} <br>
    Limit: {{r.limit}} <br>

    Durum:
    <span class="{{'ok' if r.status=='UYGUN' else 'bad'}}">
        {{r.status}}
    </span>
    </div>

    <h3>MİKSER ANALİZİ</h3>

    {% for m in r.mixers %}
    <div class="card">
        <b>Mikser {{m.mixer}}</b><br>
        Numune: {{m.count}}<br>
        Değerler: {{m.vals}}<br>
        Ortalama: {{m.avg}}<br>
        Max-Min: {{m.diff}}<br>
        Durum: <span class="{{'ok' if m.status=='OK' else 'bad'}}">{{m.status}}</span>
    </div>
    {% endfor %}

    <div class="card">
    <h3>Problemli Mikserler</h3>
    {{r.bad_mixers}}
    </div>

    {% endif %}
{% endif %}

</div>
"""

@app.route("/", methods=["GET", "POST"])
def home():

    result = None

    if request.method == "POST":
        file = request.files.get("file")

        fck, mixers, values, shape = parse_pdf(file)
        result = analyze(fck, mixers, values, shape)

    return render_template_string(HTML, r=result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
