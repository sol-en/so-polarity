import csv
import re

file_path = "../Нарахування_Оплати - Нарахування.csv"
with open(file_path, mode='r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    rows = list(reader)

# Analyze a few apartments
for apt_idx in [2, 3, 4]: # Apartments 1, 2, 3 (skipping header)
    row = rows[apt_idx]
    print(f"\nApartment {row[0]}: {row[1]}")
    for i, val in enumerate(row):
        if re.search(r'\d{2}\.\d{2}\.2026', val):
            print(f"Index {i}: Date {val}, Payment {row[i+1] if i+1 < len(row) else 'N/A'}, Balance {row[i+2] if i+2 < len(row) else 'N/A'}")
