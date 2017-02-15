# -*- coding: utf-8 -*-

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


cardpop_xlsx_path = 'data/cardpop23.xlsx'
cardpop_json_path = 'data/cardpop23.json'


wb = load_workbook(cardpop_xlsx_path)

ws = wb['Sheet1']

cards = []
decks = []

for i, row in enumerate(ws.iter_rows()):
    # first row is card names
    if i==0:
        for j, cell in enumerate(row):
            if j:
                cards.append(cell.value)
    # row 2-101 are card data
    elif i<101:
        deck = []
        for j, cell in enumerate(row):
            if j>0 and cell.value is not None:
                deck.append(cards[j-1])
        decks.append(deck)

with open(cardpop_json_path, encoding='utf-8', mode='w') as f:
    json.dump(decks, f, indent=4, sort_keys=True, separators=(',',' : '))

print(str(decks))
print(len(decks))




