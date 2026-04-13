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

            mixer_col = None
            value_col = None

            # 🔥 DOĞRU SÜTUNLARI BUL
            for i, h in enumerate(header):
                h_str = str(h).lower()

                if "mikser" in h_str:
                    mixer_col = i

                if "28" in h_str and "numune" in h_str:
                    value_col = i

            if mixer_col is None or value_col is None:
                continue

            for row in table[1:]:

                if not row:
                    continue

                try:
                    mixer_raw = str(row[mixer_col]).strip()

                    if not mixer_raw.isdigit():
                        continue

                    mixer = mixer_raw

                    val_raw = str(row[value_col]).replace(",", ".").replace("*", "").strip()

                    if val_raw == "" or val_raw.lower() == "none":
                        continue

                    # 🔥 ORTALAMA SÜTUNUNU ENGELLE
                    if len(val_raw) > 5:
                        continue

                    value = float(val_raw)

                    if 30 < value < 70:
                        mixers.setdefault(mixer, []).append(value)

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

        m_status = "OK" if (dist_ok and strength_ok) else "PROBLEM"

        if m_status == "PROBLEM":
            bad_mixers.append(m)

        mixer_results.append({
            "mixer": m,
            "vals": [round(v,1) for v in vals],
            "avg": round(m_avg, 2),
            "diff": round(diff, 2),
            "limit": round(limit_diff, 2),
            "status": m_status
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
    font-family: 'Segoe UI';
    background: linear-gradient(135deg,#0f172a,#1e293b);
    color:white;
    margin:0;
}

.container {
    max-width:900px;
    margin:auto;
    padding:40px;
}

.header {
    text-align:center;
    margin-bottom:30px;
}

.card {
    background:#1e293b;
    padding:20px;
    border-radius:12px;
    margin-top:20px;
    box-shadow:0 4px 10px rgba(0,0,0,0.4);
}

.ok { color:#22c55e; }
.bad { color:#ef4444; }

.upload {
    background:#334155;
    padding:20px;
    border-radius:12px;
    text-align:center;
}

button {
    background:#3b82f6;
    border:none;
    padding:12px 25px;
    border-radius:8px;
    color:white;
    font-size:16px;
    cursor:pointer;
}

button:hover {
    background:#2563eb;
}
</style>

<div class="container">

<div class="header">
<h1>Beton Analiz Sistemi</h1>
</div>

<div class="upload">
<form method="post" enctype="multipart/form-data">
<input type="file" name="file"><br><br>
<button type="submit">Analiz Et</button>
</form>
</div>

{% if r %}
    {% if r.error %}
        <p class="bad">{{r.error}}</p>
    {% else %}

    <div class="card">
    <h3>Genel Sonuç</h3>
    Tip: {{r.shape}}<br>
    Fck: {{r.fck}}<br>
    Numune: {{r.numune}}<br>
    Ortalama: {{r.ortalama}}<br>
    Minimum: {{r.min}}<br>
    Limit: {{r.limit}}<br>
    Durum: <span class="{{'ok' if r.status=='UYGUN' else 'bad'}}">{{r.status}}</span>
    </div>

    {% for m in r.mixers %}
    <div class="card">
    <b>Mikser {{m.mixer}}</b><br>
    {{m.vals}}<br>
    Ortalama: {{m.avg}}<br>
    Fark: {{m.diff}}<br>
    Durum: <span class="{{'ok' if m.status=='OK' else 'bad'}}">{{m.status}}</span>
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
