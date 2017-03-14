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
import os
import io
import datetime
import asyncio
import discord

import operator
import string

from discord import Message
from discord import Server
from discord.ext import commands
from discord.ext.commands import Command
from discord.ext.commands import Context

from __main__ import send_cmd_help
from cogs.utils.dataIO import dataIO
from cogs.utils import checks
from cogs.utils.chat_formatting import pagify



try:
    import nltk
except ImportError:
    raise ImportError("Please install the nltk package from pip") from None

PATH_LIST = ['data', 'tldr']
PATH = os.path.join(*PATH_LIST)
JSON = os.path.join(*PATH_LIST, "settings.json")
HOST = '127.0.0.1'
INTERVAL = 5



def isPunct(word):
    return len(word) == 1 and word in string.punctuation

def isNumeric(word):
    try:
        float(word) if '.' in word else int(word)
        return True
    except ValueError:
        return False

class RakeKeywordExtractor:
    """RAKE implementation
    http://sujitpal.blogspot.com/2013/03/implementing-rake-algorithm-with-nltk.html

    rake = RakeKeywordExtractor()
    keywords = rake.extract(text, incl_scores=True)
    """

    def __init__(self):
        self.stopwords = set(nltk.corpus.stopwords.words())
        self.top_fraction = 1 # consider top third candidate keywords by score

    def _generate_candidate_keywords(self, sentences):
        phrase_list = []
        for sentence in sentences:
            words = map(lambda x: "|" if x in self.stopwords else x,
                nltk.word_tokenize(sentence.lower()))
            phrase = []
            for word in words:
                if word == "|" or isPunct(word):
                    if len(phrase) > 0:
                        phrase_list.append(phrase)
                        phrase = []
                else:
                    phrase.append(word)
        return phrase_list

    def _calculate_word_scores(self, phrase_list):
        word_freq = nltk.FreqDist()
        word_degree = nltk.FreqDist()
        for phrase in phrase_list:
            # degree = len(filter(lambda x: not isNumeric(x), phrase)) - 1
            # SML above cost error
            degree = len(list(filter(lambda x: not isNumeric(x), phrase))) - 1
            for word in phrase:
                # word_freq.inc(word)
                # SML error above:
                word_freq[word] += 1
                # word_degree.inc(word, degree) # other words
                word_degree[word] = degree
        for word in word_freq.keys():
            word_degree[word] = word_degree[word] + word_freq[word] # itself
        # word score = deg(w) / freq(w)
        word_scores = {}
        for word in word_freq.keys():
            word_scores[word] = word_degree[word] / word_freq[word]
        return word_scores

    def _calculate_phrase_scores(self, phrase_list, word_scores):
        phrase_scores = {}
        for phrase in phrase_list:
            phrase_score = 0
            for word in phrase:
                phrase_score += word_scores[word]
            phrase_scores[" ".join(phrase)] = phrase_score
        return phrase_scores

    def extract(self, text, incl_scores=False):
        sentences = nltk.sent_tokenize(text)
        phrase_list = self._generate_candidate_keywords(sentences)
        word_scores = self._calculate_word_scores(phrase_list)
        phrase_scores = self._calculate_phrase_scores(
            phrase_list, word_scores)
        sorted_phrase_scores = sorted(phrase_scores.items(),
            key=operator.itemgetter(1), reverse=True)
        n_phrases = len(sorted_phrase_scores)
        if incl_scores:
            return sorted_phrase_scores[0:int(n_phrases/self.top_fraction)]
        else:
            return map(lambda x: x[0],
                sorted_phrase_scores[0:int(n_phrases/self.top_fraction)])


class TLDR:
    """Too Lazy; Didn’t Read.

    Uses National Language Toolkit to process messages.
    """
    def __init__(self, bot):
        self.bot = bot
        self.tags = []
        self.settings = dataIO.load_json(JSON)

    def save(self):
        dataIO.save_json(JSON, self.settings)


    @commands.group(pass_context=True, no_pm=True)
    async def tldr(self, ctx: Context):
        """Too Lazy; Didn’t Read.

        Uses National Language Toolkit to process messages."""

        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @tldr.command(name="msgid", pass_context=True, no_pm=True)
    async def tldr_message_id(self, ctx: Context, message_id: str):
        """Process messsage by message id."""
        channel = ctx.message.channel
        message = await self.bot.get_message(channel, message_id)

        rake = RakeKeywordExtractor()
        keywords = rake.extract(message.content, incl_scores=True)

        await self.bot.say("original")
        await self.bot.say(message.content)
        await self.bot.say("transformed")
        for page in pagify(str(keywords), shorten_by=12):
            await self.bot.say(page)

    @tldr.command(name="msg", pass_context=True, no_pm=True)
    async def tldr_messages(self, ctx: Context, count: int, top=10):
        """Extracts keywords from last X messages."""
        channel = ctx.message.channel
        messages = []
        async for message in self.bot.logs_from(channel, limit=count+1):
            messages.append(message.content)

        rake = RakeKeywordExtractor()
        keywords = rake.extract(" ".join(messages), incl_scores=True)

        out = []
        out.append("Found keywords: ")
        for k in keywords[:top]:
            out.append("**{}** ({:.2f}), ".format(k[0], k[1]))
        for page in pagify("".join(out)[:-2], shorten_by=12):
            await self.bot.say(page)









def check_folders():
    if not os.path.exists(PATH):
        print("Creating %s folder..." % PATH)
        os.makedirs(PATH)


def check_files():
    defaults = {
        'HOST': HOST,
        'INTERVAL': INTERVAL
    }
    if not dataIO.is_valid_json(JSON):
        print("Creating empty %s" % JSON)
        dataIO.save_json(JSON, defaults)


def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(TLDR(bot))



