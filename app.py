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
            val_col = None

            # 🔥 doğru sütunları bul
            for i, h in enumerate(header):
                h_str = str(h).lower()

                if "mikser" in h_str:
                    mixer_col = i

                if "28" in h_str and "numune" in h_str:
                    val_col = i

            if mixer_col is None or val_col is None:
                continue

            for row in table[1:]:

                try:
                    mixer = str(row[mixer_col]).strip()

                    if not mixer.isdigit():
                        continue

                    raw = str(row[val_col]).replace(",", ".").replace("*", "").strip()

                    if raw == "" or raw.lower() == "none":
                        continue

                    # ❗ ortalama satırı filtrele
                    if len(raw) > 5:
                        continue

                    val = float(raw)

                    if 30 < val < 70:
                        mixers.setdefault(mixer, []).append(val)

                except:
                    continue

    # -------- FCK --------
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

    values = [v for arr in mixers.values() for v in arr]

    return fck, mixers, values, shape


# ---------------- ANALİZ ----------------
def analyze(fck, mixers, values, shape):

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

    uygun = (avg >= limit and min_val >= (fck - 4))

    mixer_results = []
    bad_mixers = []

    for m, vals in mixers.items():

        m_avg = np.mean(vals)
        diff = max(vals) - min(vals)
        limit_diff = 0.15 * m_avg

        dist_ok = diff <= limit_diff
        strength_ok = m_avg >= (fck - 4)

        status = "OK" if (dist_ok and strength_ok) else "PROBLEM"

        if status == "PROBLEM":
            bad_mixers.append(m)

        mixer_results.append({
            "m": m,
            "vals": [round(v,1) for v in vals],
            "count": len(vals),
            "avg": round(m_avg,2),
            "diff": round(diff,2),
            "limit": round(limit_diff,2),
            "status": status,
            "desc": f"{'Dağılım uygun' if dist_ok else 'Dağılım fazla'} / {'Dayanım yeterli' if strength_ok else 'Dayanım yetersiz'}"
        })

    return {
        "shape": shape,
        "fck": fck,
        "numune": len(values),
        "avg": round(avg,2),
        "min": round(min_val,2),
        "limit": limit,
        "status": "UYGUN" if uygun else "UYGUN DEĞİL",
        "mixers": mixer_results,
        "bad": bad_mixers
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
.card {
    background:#1e293b;
    padding:20px;
    border-radius:12px;
    margin-top:20px;
}
.ok {color:#22c55e;}
.bad {color:#ef4444;}
button {
    background:#3b82f6;
    border:none;
    padding:12px 25px;
    border-radius:8px;
    color:white;
}
</style>

<div class="container">

<h2>BETON ANALİZ SİSTEMİ</h2>

<form method="post" enctype="multipart/form-data">
<input type="file" name="file"><br><br>
<button>Analiz Et</button>
</form>

{% if r %}
{% if r.error %}
<p class="bad">{{r.error}}</p>
{% else %}

<div class="card">
Tip: {{r.shape}}<br>
Fck: {{r.fck}}<br>
Numune: {{r.numune}}<br>
Ortalama: {{r.avg}}<br>
Minimum: {{r.min}}<br>
Limit: {{r.limit}}<br>
Durum: <span class="{{'ok' if r.status=='UYGUN' else 'bad'}}">{{r.status}}</span>
</div>

{% for m in r.mixers %}
<div class="card">
<b>Mikser {{m.m}}</b><br>
Numune: {{m.count}}<br>
{{m.vals}}<br>
Ortalama: {{m.avg}}<br>
Fark: {{m.diff}} (Limit: {{m.limit}})<br>
Durum: <span class="{{'ok' if m.status=='OK' else 'bad'}}">{{m.status}}</span><br>
{{m.desc}}
</div>
{% endfor %}

<div class="card">
Problemli Mikserler: {{r.bad}}
</div>

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
