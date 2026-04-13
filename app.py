from flask import Flask, request, render_template_string
import pdfplumber
import numpy as np
import re

app = Flask(__name__)

def parse_pdf(file):

    text = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += "\n" + t

    lines = text.split("\n")

    mixers = {}
    current_mixer = None

    for line in lines:

        # mikser numarası yakala
        mixer_match = re.search(r"\b(\d{1,2})\b", line)

        # 28 günlük değerleri yakala (örn: 43,3 veya 43.3)
        values = re.findall(r"\d{2,3}[.,]\d", line)

        if mixer_match:
            current_mixer = mixer_match.group(1)

        if current_mixer and values:
            for v in values:
                try:
                    val = float(v.replace(",", "."))

                    # filtre (gerçek beton aralığı)
                    if 30 < val < 70:
                        mixers.setdefault(current_mixer, []).append(val)

                except:
                    continue

    # -------- FCK --------
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

    # 🔥 sadece 28 günlükleri almak için:
    # her mikserden ilk 3 değeri al (senin formatına göre)
    cleaned_mixers = {}

    for m, vals in mixers.items():
        if len(vals) >= 3:
            cleaned_mixers[m] = vals[-3:]

    values = [v for arr in cleaned_mixers.values() for v in arr]

    return fck, cleaned_mixers, values, shape


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

        m_avg = np.mean(vals)
        diff = max(vals) - min(vals)
        limit_diff = 0.15 * m_avg

        dist_ok = diff <= limit_diff
        strength_ok = m_avg >= (fck - 4)

        m_status = "OK" if (dist_ok and strength_ok) else "PROBLEM"

        if m_status == "PROBLEM":
            bad_mixers.append(m)

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
        "mixers": mixer_results,
        "bad_mixers": bad_mixers
    }


HTML = """
<style>
body {
    font-family: Arial;
    background: linear-gradient(135deg,#0f172a,#1e293b);
    color:white;
    padding:40px;
}

.container {
    max-width:900px;
    margin:auto;
}

.card {
    background:#1e293b;
    padding:20px;
    border-radius:12px;
    margin-top:20px;
}

button {
    background:#22c55e;
    color:white;
    padding:12px 25px;
    border:none;
    border-radius:8px;
    font-size:16px;
}

input {
    margin-bottom:10px;
}
</style>

<div class="container">
<h2>BETON ANALİZ</h2>

<form method="post" enctype="multipart/form-data">
<input type="file" name="file"><br>
<button type="submit">Analiz Et</button>
</form>

{% if r %}
    {% if r.error %}
        <p>{{r.error}}</p>
    {% else %}

    <div class="card">
    Fck: {{r.fck}}<br>
    Numune: {{r.numune}}<br>
    Ortalama: {{r.ortalama}}<br>
    Minimum: {{r.min}}<br>
    Durum: {{r.status}}
    </div>

    {% for m in r.mixers %}
    <div class="card">
    Mikser {{m.mixer}}<br>
    {{m.vals}}<br>
    Ortalama: {{m.avg}}<br>
    Durum: {{m.status}}
    </div>
    {% endfor %}

    {% endif %}
{% endif %}

</div>
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
