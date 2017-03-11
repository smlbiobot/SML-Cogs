import csv
import json
crtexts_path = "data/crtexts.csv"
crtexts = {}

with open(crtexts_path, mode='r') as f:
    reader = csv.reader(f, delimiter=',')
    for row in reader:
        crtexts = { row[0]:row[1] for row in reader}

with open("data/crtexts.json", encoding='utf-8', mode="w") as f:
    json.dump(crtexts, f, indent=4,sort_keys=True,
        separators=(',',' : '))

# print(crtexts)