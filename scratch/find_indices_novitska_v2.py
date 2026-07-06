import csv

file_path = "../Нарахування_Оплати - Нарахування.csv"
with open(file_path, mode='r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    rows = list(reader)

def normalize(val):
    return val.replace(',', '.').replace('\xa0', '').replace(' ', '').strip()

for r in rows:
    if "Новицка" in r[1]:
        for i, val in enumerate(r):
            norm = normalize(val)
            if norm == "6162.66":
                print(f"Found 6162.66 at index {i}")
            if norm == "6419.31":
                print(f"Found 6419.31 at index {i}")
