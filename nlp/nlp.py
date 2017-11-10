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
from collections import OrderedDict
import discord
from discord.ext import commands
from discord.ext.commands import Context
from cogs.utils import checks
from cogs.utils.dataIO import dataIO

PATH = os.path.join("data", "nlp")
JSON = os.path.join(PATH, "settings.json")

try:
    import textblob
    from textblob import TextBlob
except ImportError:
    raise ImportError("Please install the textblob package from pip") from None

LANG = OrderedDict([
    ("af", "Afrikaans"),
    ("ar", "Arabic"),
    ("hy", "Armenian"),
    ("be", "Belarusian"),
    ("bg", "Bulgarian"),
    ("ca", "Catalan"),
    ("zh-cn", "Chinese (Simplified)"),
    ("zh-tw", "Chinese (Traditional)"),
    ("hr", "Croatian"),
    ("cs", "Czech"),
    ("da", "Danish"),
    ("nl", "Dutch"),
    ("en", "English"),
    ("eo", "Esperanto"),
    ("et", "Estonian"),
    ("tl", "Filipino"),
    ("fi", "Finnish"),
    ("fr", "French"),
    ("de", "German"),
    ("el", "Greek"),
    ("iw", "Hebrew"),
    ("hi", "Hindi"),
    ("hu", "Hungarian"),
    ("is", "Icelandic"),
    ("id", "Indonesian"),
    ("it", "Italian"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("lv", "Latvian"),
    ("lt", "Lithuanian"),
    ("no", "Norwegian"),
    ("fa", "Persian"),
    ("pl", "Polish"),
    ("pt", "Portuguese"),
    ("ro", "Romanian"),
    ("ru", "Russian"),
    ("sr", "Serbian"),
    ("sk", "Slovak"),
    ("sl", "Slovenian"),
    ("es", "Spanish"),
    ("sw", "Swahili"),
    ("sv", "Swedish"),
    ("th", "Thai"),
    ("tr", "Turkish"),
    ("uk", "Ukrainian"),
    ("vi", "Vietnamese")
])

class NLP:
    """Natural Launguage Processing.
    """

    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    @commands.command(pass_context=True)
    async def translate(self, ctx: Context, to_lang: str, *, text: str):
        """Translate to another language.

        Example:
        !translate es Simple is better than complex.
        will translate sentence to Spanish.

        !translatelang
        will list all the supported languages
        """
        blob = TextBlob(text)
        out = blob.translate(to=to_lang)
        await self.bot.say(out)

    @commands.command(pass_context=True)
    async def translatelang(self, ctx: Context):
        """List the langauge code supported by translation."""
        out = ["**{}**: {}".format(k, v) for k, v in LANG.items()]
        await self.bot.say(", ".join(out))

    @commands.command(pass_context=True)
    async def sentiment(self, ctx: Context, *, text: str):
        """Return sentiment analysis of a text."""
        blob = TextBlob(text)
        stmt = blob.sentiment
        await self.bot.say(
            "Polairty: {0.polarity}\n"
            "Subjectivity: {0.subjectivity}"
            "".format(stmt))

    @commands.command(pass_context=True)
    async def spellcheck(self, ctx: Context, *, text: str):
        """Auto-correct spelling mistakes."""
        b = TextBlob(text)
        await self.bot.say(b.correct())

    @commands.command(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_server=True)
    async def autotranslate(self, ctx, *languages):
        """Set auto-translate language or disable it.

        Use 0 as language to disable auto-translation."""
        server = ctx.message.server
        if server.id not in self.settings:
            self.settings[server.id] = {}
        on_off = True
        if languages[0].lower() in ['off', '0', 'false']:
            on_off = False
        self.settings[server.id]["AUTO_TRANSLATE"] = on_off
        self.settings[server.id]["LANGUAGE"] = languages
        if on_off:
            self.settings[server.id]["CHANNEL"] = ctx.message.channel.id
            for lang in languages:
                language = LANG.get(lang)
                if language:
                    await self.bot.say(
                        "Auto-translating messages to {} in {}".format(
                            lang, ctx.message.channel))
        else:
            await self.bot.say(
                "Auto-translate disabled.")
        dataIO.save_json(JSON, self.settings)

    async def on_message(self, msg: discord.Message):
        """Auto-translate if enabled."""
        server = msg.server
        if server is None:
            return
        if not server.id:
            return
        if server.id not in self.settings:
            return
        if "AUTO_TRANSLATE" not in self.settings[server.id]:
            return
        if msg.channel is None:
            return
        if msg.channel.id != self.settings[server.id]["CHANNEL"]:
            return
        if msg.author == server.me:
            return
        if msg.author.bot:
            return
        if self.settings[server.id]["AUTO_TRANSLATE"]:
            blob = TextBlob(msg.content)
            detected_lang = blob.detect_language()
            out = []
            for language in self.settings[server.id]["LANGUAGE"]:
                if language != detected_lang:
                    try:
                        translated_msg = blob.translate(to=language)
                        out.append(
                            "`{}` {}".format(
                                language, translated_msg))
                    except (textblob.exceptions.NotTranslated,
                            textblob.exceptions.TranslatorError):
                        pass
            if len(out):
                out.insert(0,
                           "{}\n`{}` {}".format(
                               msg.author.display_name,
                               detected_lang,
                               msg.content))
                await self.bot.send_message(msg.channel, '\n'.join(out))


def check_folder():
    """Check folder."""
    if not os.path.exists(PATH):
        os.makedirs(PATH)


def check_file():
    """Check settings."""
    defaults = {}
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, defaults)


def setup(bot):
    """Setup cog."""
    check_folder()
    check_file()
    n = NLP(bot)
    bot.add_cog(n)
