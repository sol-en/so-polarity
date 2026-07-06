import csv

file_path = "../Нарахування_Оплати - Нарахування.csv"
with open(file_path, mode='r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    rows = list(reader)

for r in rows:
    if "Новицка" in r[1]:
        for i, val in enumerate(r):
            if "6 162,66" in val or "6162.66" in val.replace(',', '.'):
                print(f"Found 6162.66 at index {i}")
            if "6 419,31" in val or "6419.31" in val.replace(',', '.'):
                print(f"Found 6419.31 at index {i}")
