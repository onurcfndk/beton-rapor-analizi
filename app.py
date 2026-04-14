from flask import Flask, request, render_template_string
import pdfplumber
import re

app = Flask(__name__)

# -------------------------------
# SAYI TEMİZLEME ( * ve , düzelt )
# -------------------------------
def temizle_sayi(text):
    if not text:
        return None
    text = str(text)
    text = text.replace("*", "").replace(",", ".")
    try:
        return float(text)
    except:
        return None

# -------------------------------
# PDF OKUMA (EN KRİTİK KISIM)
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

            # -------------------
            # BETON SINIFI
            # -------------------
            if not beton_sinifi:
                match = re.search(r'C(\d+)/(\d+)', text)
                if match:
                    beton_sinifi = (int(match.group(1)), int(match.group(2)))

            # -------------------
            # NUMUNE TİPİ
            # -------------------
            if not numune_tipi:
                if "Silindir" in text:
                    numune_tipi = "silindir"
                elif "Küp" in text:
                    numune_tipi = "kup"

            # -------------------
            # TABLO SATIR OKUMA
            # -------------------
            tables = page.extract_tables()

            for table in tables:
                for row in table:
                    if not row or len(row) < 5:
                        continue

                    try:
                        mikser = str(row[1]).strip()
                    except:
                        continue

                    # Mikser numeric değilse geç
                    if not mikser.isdigit():
                        continue

                    # 28 günlük kolon genelde sondan 2. veya 3.
                    adaylar = row[-3:]

                    deger = None
                    for a in adaylar:
                        deger = temizle_sayi(a)
                        if deger:
                            break

                    if not deger:
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

    # FCK BELİRLE
    if beton_sinifi:
        if numune_tipi == "silindir":
            fck = beton_sinifi[0]
        else:
            fck = beton_sinifi[1]
    else:
        fck = 30

    numune = len(values)
    ortalama = round(sum(values)/numune, 2)
    minimum = round(min(values), 2)

    # TS KURALI
    mikser_sayisi = len(mixers)

    if mikser_sayisi == 1:
        limit = fck
    elif 2 <= mikser_sayisi <= 4:
        limit = fck + 1
    else:
        limit = fck + 2

    durum = "UYGUN" if (ortalama >= limit and minimum >= (fck - 4)) else "UYGUN DEĞİL"

    # -------------------
    # MİKSER ANALİZ
    # -------------------
    mikser_sonuclari = []

    for m, vals in sorted(mixers.items(), key=lambda x: int(x[0])):

        ort = round(sum(vals)/len(vals), 2)
        fark = round(max(vals) - min(vals), 2)
        limit_fark = round(ort * 0.15, 2)

        dagilim = "UYGUN" if fark <= limit_fark else "PROBLEM"
        dayanım = "YETERLİ" if ort >= (fck - 4) else "DÜŞÜK"

        genel = "OK" if dagilim == "UYGUN" and dayanım == "YETERLİ" else "PROBLEM"

        mikser_sonuclari.append({
            "no": m,
            "vals": vals,
            "ort": ort,
            "fark": fark,
            "limit": limit_fark,
            "durum": genel,
            "dagilim": dagilim,
            "dayanim": dayanım
        })

    return {
        "fck": fck,
        "numune": numune,
        "ortalama": ortalama,
        "minimum": minimum,
        "limit": limit,
        "durum": durum,
        "tip": numune_tipi,
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
body { font-family: Arial; background:#0f172a; color:white; padding:30px;}
.container { max-width:900px; margin:auto; }
.card { background:#1e293b; padding:20px; border-radius:10px; margin-top:20px;}
.ok { color:#22c55e; }
.bad { color:#ef4444; }
button {
 background:#3b82f6; color:white; padding:10px 20px;
 border:none; border-radius:8px; cursor:pointer;
}
input { margin-bottom:10px; }
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

<p>Kriter:</p>
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

<p class="{{'ok' if m.dagilim=='UYGUN' else 'bad'}}">
Dağılım {{m.dagilim}}
</p>

<p class="{{'ok' if m.dayanim=='YETERLİ' else 'bad'}}">
Dayanım {{m.dayanim}} (Limit: {{result.fck - 4}})
</p>

<p class="{{'ok' if m.durum=='OK' else 'bad'}}">
Genel: {{m.durum}}
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
