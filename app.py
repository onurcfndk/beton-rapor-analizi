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

            # 🔥 28 GÜNLÜK SÜTUNU BUL
            col_index = None
            for i, h in enumerate(header):
                if h and "28" in h and "Numune" in h:
                    col_index = i
                    break

            if col_index is None:
                continue

            # 🔥 SATIRLARI OKU
            for row in table[1:]:

                if not row or len(row) <= col_index:
                    continue

                try:
                    mixer_raw = str(row[1]).strip()

                    if not mixer_raw.isdigit():
                        continue

                    mixer = mixer_raw

                    val_raw = str(row[col_index]).replace(",", ".").replace("*", "").strip()

                    if val_raw == "" or val_raw.lower() == "none":
                        continue

                    value = float(val_raw)

                    # 🔥 GERÇEK ARALIK
                    if 30 < value < 80:
                        mixers.setdefault(mixer, []).append(value)

                except:
                    continue

    # 🔥 FCK + ŞEKİL
    match = re.search(r"C(\d{2})/(\d{2})", text)

    if "silindir" in text.lower():
        shape = "Silindir"
        fck = int(match.group(1))
    else:
        shape = "Küp"
        fck = int(match.group(2))

    values = [v for arr in mixers.values() for v in arr]

    return fck, mixers, values, shape
