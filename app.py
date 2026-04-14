from flask import Flask, request, render_template_string
import pdfplumber
import re

app = Flask(__name__)

# -------------------------------
# PDF VERİ OKUMA (DÜZELTİLDİ)
# -------------------------------
def extract_data(pdf_file):
    mixers = {}
    all_values = []
    fck = 0
    numune_tipi = "bilinmiyor"

    # Tüm texti çek
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    # Numune tipi
    if "Silindir" in text:
        numune_tipi = "silindir"
    elif "Küp" in text:
        numune_tipi = "küp"

    # Beton sınıfı
    match = re.search(r"C(\d{2})/(\d{2})", text)
    if match:
        if numune_tipi == "silindir":
            fck = int(match.group(1))
        else:
            fck = int(match.group(2))

    # Tablo okuma
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()

            for table in tables:
                for row in table:
                    if not row:
                        continue

                    try:
                        mikser = row[1]
                        val_raw = row[13]  # 28 günlük numune

                        if mikser and val_raw:
                            mikser = str(mikser).strip()

                            # yıldız ve virgül temizleme
                            val_raw = str(val_raw).replace("*", "").replace(",", ".")

                            val = float(val_raw)

                            # filtre (saçma değerleri alma)
                            if val < 10 or val > 100:
                                continue

                            if mikser not in mixers:
                                mixers[mikser] = []

                            mixers[mikser].append(val)
                            all_values.append(val)

                    except:
                        continue

    return fck, numune_tipi, mixers, all_values


# -------------------------------
# ANALİZ
# -------------------------------
def analyze(fck, mixers, all_values):
    if not all_values:
        return "PDF veri okunamadı"

    numune = len(all_values)
    ortalama = round(sum(all_values) / numune, 2)
    minimum = round(min(all_values), 2)

    # TS KONTROL
    mikser_sayisi = len(mixers)

    if mikser_sayisi == 1:
        limit = fck
    elif 2 <= mikser_sayisi <= 4:
        limit = fck + 1
    else:
        limit = fck + 2

    durum = "UYGUN" if (ortalama >= limit and minimum >= (fck - 4)) else "UYGUN DEĞİL"

    # -------------------------------
    # MİKSER ANALİZİ
    # -------------------------------
    mikser_sonuc = ""
    problemli = []

    for m, vals in mixers.items():
        ort = round(sum(vals) / len(vals), 2)
        fark = round(max(vals) - min(vals), 2)
        limit_fark = round(ort * 0.15, 2)

        dagilim = "UYGUN" if fark <= limit_fark else "PROBLEM"
        dayanım = "YETERLİ" if ort >= (fck - 4) else "YETERSİZ"

        genel = "OK" if (dagilim == "UYGUN" and dayanım == "YETERLİ") else "PROBLEM"

        if genel == "PROBLEM":
            problemli.append(m)

        mikser_sonuc += f"""
        <div class='card {"bad" if genel=="PROBLEM" else "good"}'>
        <h3>Mikser {m}</h3>
        <b>Değerler:</b> {vals}<br>
        <b>Ortalama:</b> {ort}<br>
        <b>Fark:</b> {fark} (Limit: {limit_fark})<br><br>

        <b>Dağılım:</b> {dagilim}<br>
        <b>Dayanım:</b> {dayanım} (Limit: {fck-4})<br><br>

        <b>Genel:</b> {genel}
        </div>
        """

    return f"""
    <div class='genel {"bad" if durum=="UYGUN DEĞİL" else "good"}'>
    <h2>GENEL SONUÇ</h2>

    <b>Numune Tipi:</b> {numune_tipi}<br>
    <b>Fck:</b> {fck}<br>
    <b>Numune:</b> {numune}<br>
    <b>Ortalama:</b> {ortalama}<br>
    <b>Minimum:</b> {minimum}<br>
    <b>Limit:</b> {limit}<br><br>

    <b>Durum:</b> {durum}<br><br>

    <b>Kriter:</b><br>
    Ortalama ≥ Limit<br>
    Minimum ≥ (fck - 4)
    </div>

    <h2>MİKSER ANALİZİ</h2>
    {mikser_sonuc}

    <h3>Problemli Mikserler: {problemli}</h3>
    """


# -------------------------------
# ARAYÜZ (PROFESYONEL TASARIM)
# -------------------------------
HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Beton Analiz Sistemi</title>
<style>
body {
    font-family: Arial;
    background: linear-gradient(135deg,#1e3c72,#2a5298);
    color: white;
    text-align: center;
}

.container {
    background: white;
    color: black;
    padding: 30px;
    margin: 40px auto;
    width: 80%;
    border-radius: 12px;
}

button {
    background: #2a5298;
    color: white;
    padding: 12px 25px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
}

input {
    margin: 10px;
}

.card {
    padding: 15px;
    margin: 10px;
    border-radius: 8px;
}

.good {
    background: #d4edda;
}

.bad {
    background: #f8d7da;
}

.genel {
    padding: 20px;
    margin-bottom: 20px;
    border-radius: 10px;
}
</style>
</head>

<body>
<div class="container">
<h1>BETON ANALİZ SİSTEMİ</h1>

<form method="POST" enctype="multipart/form-data">
<input type="file" name="file" required>
<br>
<button type="submit">Analiz Et</button>
</form>

<br>
{{result|safe}}
</div>
</body>
</html>
"""


# -------------------------------
# ROUTE
# -------------------------------
@app.route("/", methods=["GET", "POST"])
def home():
    result = ""

    if request.method == "POST":
        file = request.files["file"]

        fck, numune_tipi, mixers, values = extract_data(file)
        result = analyze(fck, mixers, values)

    return render_template_string(HTML, result=result)


# -------------------------------
# RUN
# -------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
