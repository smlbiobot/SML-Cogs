#!/usr/bin/env python3

import json
import os
import sys
import datetime
import string
import argparse
import matplotlib
matplotlib.use('Agg')

from matplotlib import pyplot as plt

PATH = os.path.join('..')
CARDPOP_JSON = os.path.join(PATH, 'cardpop.json')
CRDATA_JSON = os.path.join(PATH, 'clashroyale.json')
DATES_JSON = os.path.join(PATH, 'dates.json')

cardpop_range_min = 8
cardpop_range_max = 26


def load_json(filename):
    """Load json by filename."""
    with open(filename, encoding='utf-8', mode="r") as f:
        data = json.load(f)
    return data


class Plot:
    """Plot CR popularity graphs."""

    def __init__(self):
        self.crdata = load_json(CRDATA_JSON)
        self.cardpop = load_json(CARDPOP_JSON)
        self.dates = load_json(DATES_JSON)

        # init card data
        self.cards = []
        self.cards_abbrev = {}

        for card_key, card_value in self.crdata["Cards"].items():
            self.cards.append(card_key)
            self.cards_abbrev[card_key] = card_key

            if card_key.find('-'):
                self.cards_abbrev[card_key.replace('-', '')] = card_key

            aka_list = card_value["aka"]
            for aka in aka_list:
                self.cards_abbrev[aka] = card_key
                if aka.find('-'):
                    self.cards_abbrev[aka.replace('-', '')] = card_key

        self.card_w = 302
        self.card_h = 363
        self.card_ratio = self.card_w / self.card_h
        self.card_thumb_scale = 0.5
        self.card_thumb_w = int(self.card_w * self.card_thumb_scale)
        self.card_thumb_h = int(self.card_h * self.card_thumb_scale)

        self.plotfigure = 0

    def cardtrend(self, cards, filename=None, filepath=None, open=False):
        """Plot graph using cards input."""
        if not len(cards):
            print("Please enter at least one card.")
            return

        cards = list(set(cards))

        validated_cards = []

        for card in cards:
            c = card
            card = self.get_card_name(card)
            if card is None:
                print(
                    "**{}** is not a valid card name.".format(c))
            else:
                validated_cards.append(card)

        if len(validated_cards) == len(cards):

            facecolor = '#32363b'
            edgecolor = '#eeeeee'
            spinecolor = '#999999'
            footercolor = '#999999'
            labelcolor = '#cccccc'
            tickcolor = '#999999'
            titlecolor = '#ffffff'

            fig = plt.figure(
                num=1,
                figsize=(8, 6),
                dpi=192,
                facecolor=facecolor,
                edgecolor=edgecolor)
            plt.grid(b=True, alpha=0.3)

            ax = fig.add_subplot(111)

            ax.set_title('Clash Royale Card Trends', color=titlecolor)
            ax.set_xlabel('Snapshots')
            ax.set_ylabel('Usage')

            for spine in ax.spines.values():
                spine.set_edgecolor(spinecolor)

            ax.xaxis.label.set_color(labelcolor)
            ax.yaxis.label.set_color(labelcolor)
            ax.tick_params(axis='x', colors=tickcolor)
            ax.tick_params(axis='y', colors=tickcolor)

            # create labels using snapshot dates
            labels = []
            for id in range(cardpop_range_min, cardpop_range_max):
                dt = datetime.datetime.strptime(
                    self.dates[str(id)], '%Y-%m-%d')
                dtstr = dt.strftime('%b %d, %y')
                labels.append("{}\n   {}".format(id, dtstr))

            # process plot only when all the cards are valid
            for card in validated_cards:

                x = range(cardpop_range_min, cardpop_range_max)
                y = [int(self.get_cardpop_count(card, id)) for id in x]
                ax.plot(x, y, 'o-', label=self.card_to_str(card))
                plt.xticks(x, labels, rotation=70, fontsize=8, ha='right')

            # make tick label font size smaller
            # for tick in ax.xaxis.get_major_ticks():
            #     tick.label.set_fontsize(8)

            leg = ax.legend(facecolor=facecolor, edgecolor=spinecolor)
            for text in leg.get_texts():
                text.set_color(labelcolor)

            ax.annotate(
                'Compiled with data from Woody’s popularity snapshots',

                # The point that we'll place the text in relation to
                xy=(0, 0),
                # Interpret the x as axes coords, and the y as figure
                # coords
                xycoords=('figure fraction'),

                # The distance from the point that the text will be at
                xytext=(15, 10),
                # Interpret `xytext` as an offset in points...
                textcoords='offset points',

                # Any other text parameters we'd like
                size=8, ha='left', va='bottom', color=footercolor)

            plt.subplots_adjust(left=0.1, right=0.96, top=0.9, bottom=0.2)

            plot_filename = "{}-plot.svg".format("-".join(cards))
            if filepath is not None:
                plot_filename = os.path.join(filepath, plot_filename)
            elif filename is not None:
                plot_filename = filename

            plt.savefig(
                plot_filename, format="svg", facecolor=facecolor,
                edgecolor=edgecolor, transparent=True)

            fig.clf()

            if open:
                os.system("open {}".format(plot_filename))

        plt.clf()
        plt.cla()



    def card_to_str(self, card=None):
        """Return name in title case."""
        if card is None:
            return None
        return string.capwords(card.replace('-', ' '))

    def get_card_name(self, card=None):
        """Return standard name used in data files."""
        if card is None:
            return None
        if card.lower() in self.cards_abbrev:
            return self.cards_abbrev[card.lower()]
        return None

    def get_cardpop_count(self, card=None, snapshot_id=None):
        """Return card popularity count by snapshot id."""
        out = 0
        snapshot_id = str(snapshot_id)
        if card is not None and snapshot_id is not None:
            if snapshot_id in self.cardpop:
                cardpop = self.cardpop[snapshot_id]["cardpop"]
                cpid = self.get_card_cpid(card)
                if cpid in cardpop:
                    out = cardpop[cpid]["count"]
        return out

    def get_cardpop(self, card=None, snapshot_id=None):
        """Return card popularity by snapshot id.

        Format: Count (Change)
        """
        out = "---"
        snapshot_id = str(snapshot_id)

        if card is not None and snapshot_id is not None:
            if snapshot_id in self.cardpop:
                cardpop = self.cardpop[snapshot_id]["cardpop"]
                cpid = self.get_card_cpid(card)
                if cpid in cardpop:
                    out = "**{}** ({})".format(
                        cardpop[cpid]["count"],
                        cardpop[cpid]["change"])
        return out

    def get_card_cpid(self, card=None):
        """Return the card populairty ID used in data."""
        # return self.crdata["Cards"][card]["cpid"]
        return card

    def get_card_from_cpid(self, cpid=None):
        """Return the card id from cpid."""
        return cpid

    def get_deckpop_count(self, deck=None, snapshot_id=None):
        """Return the deck popularity by snapshot id."""
        out = 0
        snapshot_id = str(snapshot_id)
        if snapshot_id in self.cardpop:
            decks = self.cardpop[snapshot_id]["decks"]
            if deck in decks:
                out = decks[deck]["count"]
        return out


def main(arguments):
    """Main."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        'cards', help='Card names', nargs='*')
    parser.add_argument(
        '--out', '-o', help='Output filename', default=None)
    parser.add_argument(
        '--path', '-p', help='Path to output', default=None)
    parser.add_argument(
        '--open', help='Open file when done', action='store_true')
    args = parser.parse_args(arguments)

    p = Plot()
    p.cardtrend(
        args.cards, filename=args.out, filepath=args.path, open=args.open)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
