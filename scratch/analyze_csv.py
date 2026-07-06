import csv

file_path = "../Нарахування_Оплати - Нарахування.csv"
with open(file_path, mode='r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    # Read first few rows to understand structure
    rows = []
    for _ in range(5):
        rows.append(next(reader))

# Print row 3 (Apt 1) columns with indices
for i, val in enumerate(rows[2]):
    print(f"{i}: {val}")
