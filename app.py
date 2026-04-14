from flask import Flask, request, render_template_string
import pdfplumber
import re

app = Flask(__name__)

# -------------------------------
# SAYI TEMİZLE
# -------------------------------
def temizle_sayi(text):
    if not text:
        return None
    text = str(text).replace("*", "").replace(",", ".").strip()
    try:
        return float(text)
    except:
        return None

# -------------------------------
# PDF PARSE (DÜZELTİLMİŞ)
# -------------------------------
def parse_pdf(file):
    mixers = {}
    all_values = []
    beton_sinifi = None
    numune_tipi = None

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:

            text = page.extract_text()
            if not text:
                continue

            # Beton sınıfı
            if not beton_sinifi:
                match = re.search(r'C(\d+)/(\d+)', text)
                if match:
                    beton_sinifi = (int(match.group(1)), int(match.group(2)))

            # Numune tipi
            if not numune_tipi:
                if "Silindir" in text:
                    numune_tipi = "silindir"
                elif "Küp" in text:
                    numune_tipi = "kup"

            tables = page.extract_tables()

            for table in tables:
                for row in table:
                    if not row or len(row) < 10:
                        continue

                    mikser = str(row[1]).strip()

                    # sadece numeric mikser al
                    if not mikser.isdigit():
                        continue

                    # ✅ SADECE 28 GÜNLÜK NUMUNE KOLONU
                    deger = temizle_sayi(row[-2])

                    if not deger:
                        continue

                    # saçma veri filtre
                    if deger < 10 or deger > 100:
                        continue

                    mixers.setdefault(mikser, []).append(deger)
                    all_values.append(deger)

    if not all_values:
        raise Exception("PDF veri okunamadı")

    return mixers, all_values, beton_sinifi, numune_tipi


# -------------------------------
# ANALİZ
# -------------------------------
def analyze(mixers, values, beton_sinifi, numune_tipi):

    # FCK
    if beton_sinifi:
        if numune_tipi == "silindir":
            fck = beton_sinifi[0]
        else:
            fck = beton_sinifi[1]
    else:
        fck = 30

    numune = len(values)
    ortalama = round(sum(values) / numune, 2)
    minimum = round(min(values), 2)

    mikser_sayisi = len(mixers)

    if mikser_sayisi == 1:
        limit = fck
    elif 2 <= mikser_sayisi <= 4:
        limit = fck + 1
    else:
        limit = fck + 2

    durum = "UYGUN" if (ortalama >= limit and minimum >= (fck - 4)) else "UYGUN DEĞİL"

    mikser_sonuclari = []

    for m, vals in sorted(mixers.items(), key=lambda x: int(x[0])):

        ort = round(sum(vals) / len(vals), 2)
        fark = round(max(vals) - min(vals), 2)
        limit_fark = round(ort * 0.15, 2)

        dagilim_ok = fark <= limit_fark
        dayanim_ok = ort >= (fck - 4)

        mikser_sonuclari.append({
            "no": m,
            "vals": vals,
            "ort": ort,
            "fark": fark,
            "limit": limit_fark,
            "dagilim": dagilim_ok,
            "dayanim": dayanim_ok,
            "durum": dagilim_ok and dayanim_ok
        })

    return {
        "tip": numune_tipi,
        "fck": fck,
        "numune": numune,
        "ortalama": ortalama,
        "minimum": minimum,
        "limit": limit,
        "durum": durum,
        "mikserler": mikser_sonuclari
    }


# -------------------------------
# HTML (PROFESYONEL)
# -------------------------------
HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Beton Analiz</title>
<style>
body {
 background: linear-gradient(135deg, #0f172a, #1e293b);
 color: white;
 font-family: Arial;
 padding: 30px;
}

.container { max-width: 900px; margin: auto; }

.card {
 background: #1e293b;
 padding: 20px;
 border-radius: 12px;
 margin-top: 20px;
 box-shadow: 0 0 15px rgba(0,0,0,0.4);
}

.ok { color: #22c55e; }
.bad { color: #ef4444; }

button {
 background: #3b82f6;
 padding: 12px 20px;
 border: none;
 border-radius: 8px;
 color: white;
 cursor: pointer;
}

input { margin-bottom: 15px; }
</style>
</head>
<body>

<div class="container">
<h1>BETON ANALİZ SİSTEMİ</h1>

<form method="post" enctype="multipart/form-data">
<input type="file" name="file">
<button type="submit">Analiz Et</button>
</form>

{% if result %}
<div class="card">
<h2>GENEL</h2>
<p>Numune Tipi: {{result.tip}}</p>
<p>Fck: {{result.fck}}</p>
<p>Numune: {{result.numune}}</p>
<p>Ortalama: {{result.ortalama}}</p>
<p>Minimum: {{result.minimum}}</p>
<p>Limit: {{result.limit}}</p>
<p class="{{'ok' if result.durum=='UYGUN' else 'bad'}}">{{result.durum}}</p>

<p><b>Kriter:</b></p>
<p>Ortalama ≥ Limit</p>
<p>Minimum ≥ (fck - 4)</p>
</div>

<div class="card">
<h2>MİKSER ANALİZİ</h2>

{% for m in result.mikserler %}
<p><b>Mikser {{m.no}}</b></p>
<p>Değerler: {{m.vals}}</p>
<p>Ortalama: {{m.ort}}</p>
<p>Fark: {{m.fark}} (Limit: {{m.limit}})</p>

<p class="{{'ok' if m.dagilim else 'bad'}}">
Dağılım {{'UYGUN' if m.dagilim else 'PROBLEM'}}
</p>

<p class="{{'ok' if m.dayanim else 'bad'}}">
Dayanım {{'YETERLİ' if m.dayanim else 'DÜŞÜK'}} (Limit: {{result.fck - 4}})
</p>

<p class="{{'ok' if m.durum else 'bad'}}">
Genel: {{'OK' if m.durum else 'PROBLEM'}}
</p>
<hr>
{% endfor %}
</div>
{% endif %}
</div>
</body>
</html>
"""

# -------------------------------
# ROUTE
# -------------------------------
@app.route("/", methods=["GET", "POST"])
def home():
    result = None

    if request.method == "POST":
        file = request.files["file"]

        if file:
            try:
                mixers, values, sinif, tip = parse_pdf(file)
                result = analyze(mixers, values, sinif, tip)
            except Exception as e:
                return f"HATA: {str(e)}"

    return render_template_string(HTML, result=result)


# -------------------------------
# RUN
# -------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
