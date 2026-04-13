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

            for row in table:

                if not row or len(row) < 5:
                    continue

                try:
                    mixer_raw = str(row[1]).strip()

                    if not mixer_raw.isdigit():
                        continue

                    mixer = mixer_raw

                    val_raw = str(row[-2]).replace(",", ".").replace("*", "").strip()

                    if val_raw == "" or val_raw.lower() == "none":
                        continue

                    value = float(val_raw)

                    if 20 < value < 80:
                        mixers.setdefault(mixer, []).append(value)

                except:
                    continue

    # 🔥 FCK + NUMUNE TİPİ
    match = re.search(r"C(\d{2})/(\d{2})", text)
    shape = "silindir" if "silindir" in text.lower() else "kup"

    if match:
        if shape == "silindir":
            fck = int(match.group(1))  # 25
        else:
            fck = int(match.group(2))  # 30
    else:
        fck = 30

    values = [v for arr in mixers.values() for v in arr]

    return fck, mixers, values, shape


# ---------------- ANALİZ ----------------
def analyze(fck, mixers, values):

    if not values:
        return {"error": "PDF veri okunamadı"}

    avg = np.mean(values)
    min_val = min(values)

    mixer_count = len(mixers)

    # TS kuralı
    if mixer_count == 1:
        limit = fck
    elif 2 <= mixer_count <= 4:
        limit = fck + 1
    else:
        limit = fck + 2

    status = "UYGUN"
    if avg < limit or min_val < (fck - 4):
        status = "UYGUN DEĞİL"

    mixer_results = []
    bad_mixers = []

    for m, vals in mixers.items():

        if len(vals) < 2:
            continue  # çok az veri varsa atla

        m_avg = np.mean(vals)
        diff = max(vals) - min(vals)
        limit_diff = 0.15 * m_avg

        dist_ok = diff <= limit_diff
        strength_ok = m_avg >= (fck - 4)

        explanations = []

        if dist_ok:
            explanations.append("Dağılım uygun (max-min ≤ %15 ortalama)")
        else:
            explanations.append("Dağılım fazla (limit aşıldı)")

        if strength_ok:
            explanations.append(f"Dayanım yeterli (≥ {fck-4})")
        else:
            explanations.append(f"Dayanım yetersiz (< {fck-4})")

        m_status = "OK"
        if not dist_ok or not strength_ok:
            m_status = "PROBLEM"
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
body { font-family: Arial; background:#eef2f7; padding:20px; }

.header {
    background:#1f2d3d;
    color:white;
    padding:15px;
    border-radius:10px;
    margin-bottom:20px;
}

.card {
    background:white;
    padding:15px;
    margin:10px 0;
    border-radius:10px;
    box-shadow:0 2px 6px rgba(0,0,0,0.1);
}

.ok { color:green; font-weight:bold; }
.bad { color:red; font-weight:bold; }

</style>

<div class="header">
<h2>BETON ANALİZ SİSTEMİ</h2>
</div>

<form method="post" enctype="multipart/form-data">
    <input type="file" name="file">
    <button type="submit">Analiz Et</button>
</form>

{% if r %}

    {% if r.error %}
        <p class="bad">{{r.error}}</p>
    {% else %}

        <div class="card">
        <h3>GENEL SONUÇ</h3>
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
            Numune: {{m.count}} <br>
            Değerler: {{m.vals}} <br>
            Ortalama: {{m.avg}} <br>
            Max-Min: {{m.diff}} (Limit: {{m.limit}}) <br>

            Durum:
            <span class="{{'ok' if m.status=='OK' else 'bad'}}">
                {{m.status}}
            </span><br>

            <b>Açıklama:</b><br>
            {% for e in m.explanations %}
                - {{e}}<br>
            {% endfor %}
        </div>
        {% endfor %}

        <div class="card">
        <h3>Problemli Mikserler</h3>
        {{r.bad_mixers}}
        </div>

    {% endif %}

{% endif %}
"""


@app.route("/", methods=["GET", "POST"])
def home():

    result = None

    if request.method == "POST":
        file = request.files.get("file")

        fck, mixers, values, shape = parse_pdf(file)
        result = analyze(fck, mixers, values)

    return render_template_string(HTML, r=result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
