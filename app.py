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

                    # 🔥 28 GÜN DEĞER ( * temizleniyor )
                    val_raw = str(row[-2]).replace(",", ".").replace("*", "").strip()

                    if val_raw == "" or val_raw.lower() == "none":
                        continue

                    value = float(val_raw)

                    if 20 < value < 80:
                        mixers.setdefault(mixer, []).append(value)

                except:
                    continue

    # sadece 3 değer
    clean_mixers = {}
    for m, vals in mixers.items():
        if len(vals) >= 3:
            clean_mixers[m] = vals[:3]

    values = [v for arr in clean_mixers.values() for v in arr]

    # fck
    match = re.search(r"C(\d{2})/(\d{2})", text)
    fck = int(match.group(2)) if match else 30

    return fck, clean_mixers, values


# ---------------- ANALİZ ----------------
def analyze(fck, mixers, values):

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

    status = "UYGUN"
    if avg < limit or min_val < (fck - 4):
        status = "UYGUN DEĞİL"

    mixer_results = []
    bad_mixers = []

    for m, vals in mixers.items():

        m_avg = np.mean(vals)
        diff = max(vals) - min(vals)
        limit_diff = 0.15 * m_avg

        dist_ok = diff <= limit_diff
        strength_ok = m_avg >= (fck - 4)

        m_status = "OK"
        reason = []

        if not dist_ok:
            reason.append("Dağılım fazla")

        if not strength_ok:
            reason.append(f"Dayanım düşük (fck-4={fck-4})")

        if reason:
            m_status = "PROBLEM"
            bad_mixers.append(m)

        mixer_results.append({
            "mixer": m,
            "values": [round(v,1) for v in vals],
            "avg": round(m_avg, 2),
            "diff": round(diff, 2),
            "limit": round(limit_diff, 2),
            "status": m_status,
            "reason": ", ".join(reason) if reason else "Sorun yok"
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
body { font-family: Arial; padding:20px; }
.ok { color: green; font-weight: bold; }
.bad { color: red; font-weight: bold; }
.box { border:1px solid #ddd; padding:10px; margin:10px 0; border-radius:8px;}
</style>

<h2>BETON ANALİZ SİSTEMİ</h2>

<form method="post" enctype="multipart/form-data">
    <input type="file" name="file">
    <button type="submit">Analiz Et</button>
</form>

{% if r %}

    {% if r.error %}
        <p class="bad">{{r.error}}</p>
    {% else %}

        <div class="box">
        <h3>GENEL SONUÇ</h3>
        Fck: {{r.fck}} <br>
        28 Gün Numune: {{r.numune}} <br>
        Ortalama: {{r.ortalama}} <br>
        Minimum: {{r.min}} <br>
        Limit: {{r.limit}} <br>
        Durum:
        <span class="{{'ok' if r.status=='UYGUN' else 'bad'}}">
            {{r.status}}
        </span>
        </div>

        <h3>MİKSER DETAY</h3>

        {% for m in r.mixers %}
        <div class="box">
            <b>Mikser {{m.mixer}}</b><br>
            Değerler: {{m.values}} <br>
            Ortalama: {{m.avg}} <br>
            Max-Min: {{m.diff}} (Limit: {{m.limit}}) <br>
            Durum:
            <span class="{{'ok' if m.status=='OK' else 'bad'}}">
                {{m.status}}
            </span><br>
            Açıklama: {{m.reason}}
        </div>
        {% endfor %}

        <h3>Problemli Mikserler</h3>
        {{r.bad_mixers}}

    {% endif %}

{% endif %}
"""


@app.route("/", methods=["GET", "POST"])
def home():

    result = None

    if request.method == "POST":
        file = request.files.get("file")

        fck, mixers, values = parse_pdf(file)
        result = analyze(fck, mixers, values)

    return render_template_string(HTML, r=result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
