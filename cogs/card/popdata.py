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
import operator
from operator import itemgetter



cardpop_xlsx_path = 'data/cardpop{}.xlsx'
cardpop_json_path = 'data/cardpop{}.json'
cardpop_path = 'data/cardpop.json'

cardpop_range_min = 16
cardpop_range_max = 24

cardpop = {}

class Deck:
    def __init__(self, cards=None):
        self.cards = sorted(cards)
        self.name = ', '.join(self.cards)
        self.count = 1


def save_json(filename=None, data=None):
    with open(filename, encoding='utf-8', mode='w') as f:
        json.dump(data, f, indent=4, sort_keys=False, separators=(',',' : '))

def sort_by_deck_count(deck):
    return deck["count"]

def process_data():
    for id in range(cardpop_range_min, cardpop_range_max):


        wb = load_workbook(cardpop_xlsx_path.format(id))

        ws = wb.worksheets[0]

        cards = []
        players = []
        decks = {}

        for i, row in enumerate(ws.iter_rows()):
            # first row is card names
            if i==0:
                for j, cell in enumerate(row):
                    if j:
                        cards.append(cell.value)
            # row 2-101 are card data
            # for older worksheets, it’s len - 2
            elif i<101:
                deck = []
                for j, cell in enumerate(row):
                    if j>0 and cell.value == 1:
                        deck.append(cards[j-1])

                deck = sorted(deck)
                player = {
                    "rank": i,
                    "deck": deck
                }

                # Create deck count
                if len(deck):
                    players.append(player)

                    deck_id = ', '.join(deck)

                    # populate unique decks
                    if deck_id not in decks:
                        decks[deck_id] = {
                            "id": deck_id,
                            "deck": deck,
                            "count": 1
                            }
                    else:
                        decks[deck_id]["count"] += 1

        decks = sorted(decks.items(), key = lambda x: -x[1]["count"])
        decks = dict(decks)
        # decks = [{k: v} for k, v in decks.items()]
        

        cardpop[str(id)] = {
            "players": players,
            "cards": sorted(cards),
            "decks": decks
            }

    save_json(cardpop_path, cardpop)


process_data()





