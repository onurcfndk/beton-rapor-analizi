def parse_pdf(file):

    mixers = {}

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:

            table = page.extract_table()
            if not table:
                continue

            for row in table:

                if not row or len(row) < 5:
                    continue

                try:
                    mixer_raw = str(row[1]).strip()

                    # 🔥 SADECE SAYI OLAN MİKSER
                    if not mixer_raw.isdigit():
                        continue

                    mixer = mixer_raw

                    # 🔥 28 GÜNLÜK NUMUNE (SONDAN 2. SÜTUN)
                    val_raw = str(row[-2]).replace(",", ".").strip()

                    # boşsa geç (7 günlük satır)
                    if val_raw == "" or val_raw.lower() == "none":
                        continue

                    value = float(val_raw)

                    # 🔥 SADECE MANTIKLI ARALIK
                    if 20 < value < 80:
                        mixers.setdefault(mixer, []).append(value)

                except:
                    continue

    # 🔥 SADECE 3'LÜ GRUPLARI AL
    clean_mixers = {}

    for m, vals in mixers.items():
        if len(vals) == 3:   # olması gereken
            clean_mixers[m] = vals

    values = [v for arr in clean_mixers.values() for v in arr]

    # FCK
    text = ""
    with pdfplumber.open(file) as pdf:
        for p in pdf.pages:
            t = p.extract_text()
            if t:
                text += t

    import re
    match = re.search(r"C(\d{2})/(\d{2})", text)
    fck = int(match.group(2)) if match else 30

    return fck, clean_mixers, values
