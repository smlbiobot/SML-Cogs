#!/usr/bin/env python3

import os
import sys
from PIL import Image

# CONFIG = os.path.join("config.json")


# def load_json(filename):
#     """Load json by filename."""
#     with open(filename, encoding='utf-8', mode='r') as f:
#         data = json.load(f)
#     return data

EMBLEM_COLORS = ['Blue', 'Red', 'Violet', 'Green', 'Yellow']
EMBLEM_SYMBOLS = ['Skull', 'Cactus', 'Star', 'Lightning']


def generate_emblems():
    """Generate Brawl Stars emblems."""
    src_path = os.path.join('.', 'src')
    out_path = os.path.join('.', 'img')

    for i, color in enumerate(EMBLEM_COLORS):
        for j, symbol in enumerate(EMBLEM_SYMBOLS):
            # bg = Image.open(
            #     os.path.join(src_path, "{}{}.png".format(color, i + 1)))
            # img = Image.new('RGBA', bg.size, (255, 255, 255, 0))
            # img.paste(bg)
            # # symbol
            # sm_fn = "{}.png".format(symbol)
            # img
            # img.paste(
            #     Image.open(os.path.join(src_path, sm_fn)), (0, 0))

            # filename = "clan_badge_0{}_0{}.png".format(i, j)
            # filename = os.path.join(out_path, filename)
            # img.save(filename)

            filename = "clan_badge_0{}_0{}.png".format(i + 1, j + 1)
            filename = os.path.join(out_path, filename)
            bg_fn = "{}{}.png".format(color, j + 1)
            sm_fn = "{}.png".format(symbol)
            im = Image.open(os.path.join(src_path, bg_fn))
            sm_im = Image.open(os.path.join(src_path, sm_fn))
            # im.paste(sm_im, (0, 0))
            im = Image.alpha_composite(im, sm_im)
            im.save(filename)
            print(filename)


def main(arguments):
    """Main."""
    generate_emblems()


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))