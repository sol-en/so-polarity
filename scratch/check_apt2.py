import csv

file_path = "../Нарахування_Оплати - Нарахування.csv"
with open(file_path, mode='r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    rows = list(reader)

apt2 = rows[2]
for i in range(460, 485):
    print(f"{i}: {apt2[i]}")
