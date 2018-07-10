import json
import re

with open('./player_db_bak.json') as f:
    data = json.load(f)

TAG_CHARS = '0289CGJLPQRUVY'

# remove hash from keys
d0 = {}
for k, v in data.copy().items():
    _k = k.upper()
    _k = re.sub(r'[^0289CGJLPQRUVY]+', '', _k)
    d0[_k] = v

# ensure unique user ID
user_ids = []
d1 = {}
for k, v in d0.copy().items():
    user_id = v.get('user_id')
    if user_id not in user_ids:
        d1[k] = v
        user_ids.append(user_id)


# save json
with open ('./player_db_processed.json', 'w', encoding='utf-8') as f:
    json.dump(d1, f, indent=4)