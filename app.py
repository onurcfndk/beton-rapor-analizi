from flask import Flask, request, jsonify
import numpy as np

app = Flask(__name__)

def analyze(fck, values, mixer_data):
    n = len(values)
    avg = round(np.mean(values), 2)
    min_val = round(min(values), 2)

    if n == 1:
        limit = fck
    elif 2 <= n <= 4:
        limit = fck + 1
    else:
        limit = fck + 2

    status = "UYGUN"
    if avg < limit or min_val < fck - 4:
        status = "UYGUN DEĞİL"

    return {
        "avg": avg,
        "min": min_val,
        "status": status
    }


@app.route("/")
def home():
    return "Beton analiz sistemi hazır"

@app.route("/analyze", methods=["POST"])
def analyze_api():
    data = request.json
    result = analyze(
        data["fck"],
        data["values"],
        data["mixer_data"]
    )
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
