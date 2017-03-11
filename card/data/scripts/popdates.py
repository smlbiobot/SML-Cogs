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

import json
import datetime

data_path = 'data/dates.json'

cardpop_range_min = 8
cardpop_range_max = 100
cardpop_min_date = datetime.date(2016, 7, 17)

def save_json(filename=None, data=None):
    with open(filename, encoding='utf-8', mode='w') as f:
        json.dump(data, f, indent=4, sort_keys=False, separators=(',',' : '))


def process_data():

    dates = {}

    for id in range(cardpop_range_min, cardpop_range_max):
        season_days = (id - cardpop_range_min) * 14
        season_timedelta = datetime.timedelta(days=season_days)
        dates[str(id)] = cardpop_min_date + season_timedelta

    # id = 23
    # dates = {}
    # dates["23"] = datetime.date(2017, 2, 12)

    # while id > cardpop_range_min:
    #     date = dates[str(id)] - datetime.timedelta(days=14)
    #     dates[str(id - 1)] = date
    #     id -= 1

    data = {k: v.isoformat() for k, v in dates.items()}

    # for id in  range(23, cardpop_range_max):
    #     date = dates[str(id)] - datetime.timedelta(days=14)

    save_json(data_path, data)


process_data()







