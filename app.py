from flask import Flask, request, render_template_string
import pdfplumber
import numpy as np
import re

app = Flask(__name__)

def parse_pdf(file):

    mixers = {}
    text = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:

            t = page.extract_text()
            if t:
                text += "\n" + t

            table = page.extract_table()

            # ---------- 1. YÖNTEM: TABLE ----------
            if table:
                header = table[0]

                mixer_col = None
                val_col = None

                for i, h in enumerate(header):
                    h_str = str(h).lower()

                    if "mikser" in h_str:
                        mixer_col = i

                    if "28" in h_str and "numune" in h_str:
                        val_col = i

                if mixer_col is not None and val_col is not None:

                    for row in table[1:]:

                        try:
                            mixer = str(row[mixer_col]).strip()

                            if not mixer.isdigit():
                                continue

                            raw = str(row[val_col]).replace(",", ".").replace("*", "").strip()

                            if raw == "" or raw.lower() == "none":
                                continue

                            if len(raw) > 5:
                                continue

                            val = float(raw)

                            if 30 < val < 70:
                                mixers.setdefault(mixer, []).append(val)

                        except:
                            continue

    # ---------- 2. YÖNTEM: TEXT FALLBACK ----------
    if not mixers:

        lines = text.split("\n")
        current_mixer = None

        for line in lines:

            m = re.search(r"\b(\d{1,2})\b", line)
            vals = re.findall(r"\d{2,3}[.,]\d", line)

            if m:
                current_mixer = m.group(1)

            if current_mixer and vals:
                for v in vals:
                    try:
                        val = float(v.replace(",", "."))
                        if 30 < val < 70:
                            mixers.setdefault(current_mixer, []).append(val)
                    except:
                        continue

        # her mikserden son 3 değeri al
        mixers = {k: v[-3:] for k, v in mixers.items() if len(v) >= 3}

    # ---------- FCK ----------
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
    bad = []

    for m, vals in mixers.items():

        m_avg = np.mean(vals)
        max_val = max(vals)
        min_m = min(vals)

        diff = max_val - min_m
        limit_diff = 0.15 * m_avg

        # 🔥 1. Dağılım kontrolü
        dist_ok = diff <= limit_diff

        # 🔥 2. Dayanım kontrolü
        strength_ok = m_avg >= (fck - 4)

        # 🔥 GENEL DURUM
        if dist_ok and strength_ok:
            m_status = "OK"
        else:
            m_status = "PROBLEM"
            bad.append(m)

        # 🔥 AÇIKLAMA
        desc = []
        desc.append(
            f"Dağılım {'uygun' if dist_ok else 'fazla'} "
            f"(Fark: {round(diff,2)} / Limit: {round(limit_diff,2)})"
        )
        desc.append(
            f"Dayanım {'yeterli' if strength_ok else 'yetersiz'} "
            f"(Ortalama: {round(m_avg,2)} / Limit: {fck-4})"
        )

        mixer_results.append({
            "m": m,
            "vals": [round(v,1) for v in vals],
            "avg": round(m_avg,2),
            "diff": round(diff,2),
            "limit": round(limit_diff,2),
            "status": m_status,
            "desc": desc
        })

    return {
        "shape": shape,
        "fck": fck,
        "numune": len(values),
        "avg": round(avg,2),
        "min": round(min_val,2),
        "limit": limit,
        "status": status,
        "mixers": mixer_results,
        "bad": bad
    }


HTML = """
<style>
body {background:#0f172a;color:white;font-family:Arial;padding:30px;}
.card {background:#1e293b;padding:15px;margin-top:15px;border-radius:10px;}
button {background:#22c55e;padding:10px;border:none;border-radius:5px;}
.ok{color:#22c55e;} .bad{color:#ef4444;}
</style>

<h2>Beton Analiz</h2>

<form method="post" enctype="multipart/form-data">
<input type="file" name="file"><br><br>
<button>Analiz Et</button>
</form>

{% if r %}
{% if r.error %}
<p class="bad">{{r.error}}</p>
{% else %}

<div class="card">
Fck: {{r.fck}}<br>
Numune: {{r.numune}}<br>
Ortalama: {{r.avg}}<br>
Durum: <span class="{{'ok' if r.status=='UYGUN' else 'bad'}}">{{r.status}}</span>
</div>

{% for m in r.mixers %}
<div class="card">
Mikser {{m.m}}<br>
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
