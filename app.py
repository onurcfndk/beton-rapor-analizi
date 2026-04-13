from flask import Flask, request, render_template_string
import pdfplumber
import numpy as np
import re

app = Flask(__name__)

def parse_pdf(file):

    mixers = {}

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:

            table = page.extract_table()

            if not table:
                continue

            for row in table:

                if not row or len(row) < 4:
                    continue

                try:
                    # 🔥 Mikser her zaman 2. sütun
                    mixer_raw = str(row[1]).strip()

                    if not mixer_raw.isdigit():
                        continue

                    mixer = mixer_raw

                    # 🔥 Satırdaki TÜM sayıları bul
                    cells = " ".join([str(c) for c in row])

                    values = re.findall(r"\d{2,3}[.,]\d", cells)

                    for v in values:
                        val = float(v.replace(",", "."))

                        # 🔥 kritik filtre
                        if 30 < val < 70:
                            mixers.setdefault(mixer, []).append(val)

                except:
                    continue

    # 🔥 her mikserden sadece SON 3 değeri al (28 gün)
    clean_mixers = {}

    for m, vals in mixers.items():
        if len(vals) >= 3:
            clean_mixers[m] = vals[-3:]

    values = [v for arr in clean_mixers.values() for v in arr]

    # 🔥 FCK
    text = ""
    with pdfplumber.open(file) as pdf:
        for p in pdf.pages:
            t = p.extract_text()
            if t:
                text += t

    match = re.search(r"C(\d{2})/(\d{2})", text)

    if match:
        if "silindir" in text.lower():
            fck = int(match.group(1))
            shape = "Silindir"
        else:
            fck = int(match.group(2))
            shape = "Küp"
    else:
        fck = 30
        shape = "Bilinmiyor"

    return fck, clean_mixers, values, shape


def analyze(fck, mixers, values, shape):

    if not values:
        return {"error": "PDF veri okunamadı"}

    avg = np.mean(values)
    min_val = min(values)

    mixer_count = len(mixers)

    if mixer_count == 1:
        limit = fck
    elif mixer_count <= 4:
        limit = fck + 1
    else:
        limit = fck + 2

    status = "UYGUN" if (avg >= limit and min_val >= fck-4) else "UYGUN DEĞİL"

    mixer_results = []

    for m, vals in mixers.items():

        m_avg = np.mean(vals)
        diff = max(vals) - min(vals)
        limit_diff = 0.15 * m_avg

        m_status = "OK" if (diff <= limit_diff and m_avg >= fck-4) else "PROBLEM"

        mixer_results.append({
            "mixer": m,
            "vals": vals,
            "avg": round(m_avg,2),
            "diff": round(diff,2),
            "status": m_status
        })

    return {
        "shape": shape,
        "fck": fck,
        "numune": len(values),
        "ortalama": round(avg,2),
        "min": round(min_val,2),
        "limit": limit,
        "status": status,
        "mixers": mixer_results
    }


HTML = """
<style>
body {
    font-family: Arial;
    background:#0f172a;
    color:white;
    padding:30px;
}
.card {
    background:#1e293b;
    padding:15px;
    margin-top:15px;
    border-radius:10px;
}
button {
    background:#22c55e;
    padding:10px;
    border:none;
    border-radius:5px;
}
</style>

<h2>Beton Analiz</h2>

<form method="post" enctype="multipart/form-data">
<input type="file" name="file"><br><br>
<button>Analiz Et</button>
</form>

{% if r %}
{% if r.error %}
<p>{{r.error}}</p>
{% else %}

<div class="card">
Fck: {{r.fck}}<br>
Numune: {{r.numune}}<br>
Ortalama: {{r.ortalama}}<br>
Durum: {{r.status}}
</div>

{% for m in r.mixers %}
<div class="card">
Mikser {{m.mixer}}<br>
{{m.vals}}<br>
Durum: {{m.status}}
</div>
{% endfor %}

{% endif %}
{% endif %}
"""

@app.route("/", methods=["GET","POST"])
def home():
    result=None
    if request.method=="POST":
        file=request.files.get("file")
        fck,mixers,values,shape=parse_pdf(file)
        result=analyze(fck,mixers,values,shape)

    return render_template_string(HTML,r=result)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=10000)
