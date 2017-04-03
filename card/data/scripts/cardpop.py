#!/usr/bin/env python3

"""
The MIT License (MIT)

Copyright (c) 2017 SML

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from openpyxl import load_workbook
import json
import os

CARDPOP_JSON = os.path.join("..", "cardpop", "cardpop-2017-04-03.json")
CARDPOP_CSV = os.path.join("..", "cardpop", "cardpop-2017-04-03.csv")
CR_JSON = os.path.join("..", "clashroyale.json")

def load_json(filename=None):
    with open(filename, encoding='utf-8', mode="r") as f:
        json_data = json.load(f)
    return json_data

def save_json(filename=None, data=None):
    with open(filename, encoding='utf-8', mode='w') as f:
        json.dump(data, f, indent=4, sort_keys=False, separators=(',',' : '))


cardpop = load_json(CARDPOP_JSON)
clashroyale = load_json(CR_JSON)

def sfid_to_cpid(sfid:str):
    """Convert Starfire ID to Card Popularity ID"""
    cards = clashroyale["Cards"]
    for card_key, card_data in cards.items():
        if card_data["sfid"] == sfid:
            return card_data["cpid"]


def cardpop_csv():
    decks = cardpop["decks"]

    # header
    # all_cards = ['']
    all_cards = [v["cpid"] for k, v in clashroyale["Cards"].items()]

    with open(CARDPOP_CSV, 'w') as f:
        f.seek(0)
        f.write(',')
        f.write(','.join(all_cards))
        f.write('\n')
        for i, deck in enumerate(decks):
            row = [str(i + 1)]
            deckcards = []
            for deckcard in deck:
                deckcards.append(sfid_to_cpid(deckcard["key"]))
            for card in all_cards:
                if card in deckcards:
                    row.append("1")
                else:
                    row.append("")
            f.write(','.join(row))
            f.write('\n')





cardpop_csv()
