from flask import Flask, request, render_template_string
import numpy as np
import pdfplumber
import re

app = Flask(__name__)

def analyze(fck, values):
    avg = round(np.mean(values), 2)
    min_val = round(min(values), 2)

    status = "UYGUN"
    if avg < fck or min_val < fck - 4:
        status = "UYGUN DEĞİL"

    return avg, min_val, status


def extract_numbers_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""

    numbers = re.findall(r"\d+\.?\d*", text)
    return [float(n) for n in numbers]


HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Beton PDF Analiz</title>
</head>
<body>
    <h2>PDF Beton Analiz Sistemi</h2>

    <form method="post" enctype="multipart/form-data">
        Fck: <input type="number" name="fck" step="0.1"><br><br>
        PDF: <input type="file" name="file"><br><br>
        <button type="submit">Analiz Et</button>
    </form>

    {% if result %}
        <h3>Sonuç</h3>
        Ortalama: {{result[0]}} <br>
        Minimum: {{result[1]}} <br>
        Durum: {{result[2]}}
    {% endif %}
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def home():
    result = None

    if request.method == "POST":
        fck = float(request.form["fck"])
        file = request.files["file"]

        values = extract_numbers_from_pdf(file)
        result = analyze(fck, values)

    return render_template_string(HTML, result=result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
