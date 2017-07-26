import argparse
import datetime as dt
import pprint
from collections import Counter, OrderedDict

import pandas as pd
from elasticsearch_dsl import DocType, Date, Nested, Boolean, \
    analyzer, Keyword, Text, Integer
# global ES connection
from elasticsearch_dsl.connections import connections
from elasticsearch_dsl.query import Match, Range
from sparklines import sparklines

connections.create_connection(hosts=['localhost'], timeout=20)

class ServerDoc(DocType):
    """Server Inner Object."""
    id = Integer()
    name = Text(fields={'raw': Keyword()})


class ChannelDoc(DocType):
    """Channel Inner Object."""
    id = Integer()
    name = Text(fields={'raw': Keyword()})


class RoleDoc(DocType):
    """Role Inner Object."""
    id = Integer()
    name = Text(fields={'raw': Keyword()})


class UserDoc(DocType):
    """Discord user."""
    name = Text(fields={'raw': Keyword()})
    id = Integer()
    discriminator = Integer()
    bot = Boolean()
    avatar_url = Text(
        analyzer=analyzer("simple"),
        fields={'raw': Keyword()})

    class Meta:
        doc_type = 'user'


class MemberDoc(UserDoc):
    """Discord member."""
    id = Integer()
    name = Text(fields={'raw': Keyword()})
    display_name = Text(fields={'raw': Keyword()})
    bot = Boolean()
    top_role = Nested(doc_class=RoleDoc)
    roles = Nested(doc_class=RoleDoc)
    server = Nested(doc_class=ServerDoc)

    class Meta:
        doc_type = 'member'

    @classmethod
    def member_dict(cls, member):
        """Member dictionary."""
        d = {
            'id': member.id,
            'username': member.name,
            'bot': member.bot
        }
        if isinstance(member, Member):
            d.update({
                'name': member.display_name,
                'display_name': member.display_name,
                'roles': [
                    {'id': r.id, 'name': r.name} for r in member.roles
                ],
                'top_role': {
                    'id': member.top_role.id,
                    'name': member.top_role.name
                },
                'joined_at': member.joined_at
            })
        return d


class MemberJoinDoc(MemberDoc):
    """Discord member join"""

    class Meta:
        doc_type = 'member_join'

    @classmethod
    def log(cls, member, **kwargs):
        pass


class MemberJoinDoc(MemberDoc):
    """Discord member join"""

    class Meta:
        doc_type = 'member_join'

    @classmethod
    def log(cls, member, **kwargs):
        pass


class MessageDoc(DocType):
    """Discord Message."""
    id = Integer()
    content = Text(
        analyzer=analyzer("simple"),
        fields={'raw': Keyword()}
    )
    author = Nested(doc_class=MemberDoc)
    server = Nested(doc_class=ServerDoc)
    channel = Nested(doc_class=ChannelDoc)
    mentions = Nested(doc_class=MemberDoc)
    timestamp = Date()

    class Meta:
        doc_type = 'message'

    @classmethod
    def log(cls, message, **kwargs):
        """Log all."""
        doc = MessageDoc(
            content=message.content,
            embeds=message.embeds,
            attachments=message.attachments,
            id=message.id,
            timestamp=dt.datetime.utcnow()
        )
        doc.set_server(message.server)
        doc.set_channel(message.channel)
        doc.set_author(message.author)
        doc.set_mentions(message.mentions)
        doc.save(**kwargs)

    def set_author(self, author):
        """Set author."""
        self.author = MemberDoc.member_dict(author)

    def set_server(self, server):
        """Set server."""
        self.server = {
            'id': server.id,
            'name': server.name
        }

    def set_channel(self, channel):
        """Set channel."""
        self.channel = {
            'id': channel.id,
            'name': channel.name,
            'is_default': channel.is_default,
            'position': channel.position
        }

    def set_mentions(self, mentions):
        """Set mentions."""
        self.mentions = [MemberDoc.member_dict(m) for m in mentions]

    def save(self, **kwargs):
        return super(MessageDoc, self).save(**kwargs)


class MessageDoc(DocType):
    """Discord Message."""
    id = Integer()
    content = Text(
        analyzer=analyzer("simple"),
        fields={'raw': Keyword()}
    )
    author = Nested(doc_class=MemberDoc)
    server = Nested(doc_class=ServerDoc)
    channel = Nested(doc_class=ChannelDoc)
    mentions = Nested(doc_class=MemberDoc)
    timestamp = Date()

    class Meta:
        doc_type = 'message'

    @classmethod
    def log(cls, message, **kwargs):
        """Log all."""
        doc = MessageDoc(
            content=message.content,
            embeds=message.embeds,
            attachments=message.attachments,
            id=message.id,
            timestamp=dt.datetime.utcnow()
        )
        doc.set_server(message.server)
        doc.set_channel(message.channel)
        doc.set_author(message.author)
        doc.set_mentions(message.mentions)
        doc.save(**kwargs)

    def set_author(self, author):
        """Set author."""
        self.author = MemberDoc.member_dict(author)

    def set_server(self, server):
        """Set server."""
        self.server = {
            'id': server.id,
            'name': server.name
        }

    def set_channel(self, channel):
        """Set channel."""
        self.channel = {
            'id': channel.id,
            'name': channel.name,
            'is_default': channel.is_default,
            'position': channel.position
        }

    def set_mentions(self, mentions):
        """Set mentions."""
        self.mentions = [MemberDoc.member_dict(m) for m in mentions]

    def save(self, **kwargs):
        return super(MessageDoc, self).save(**kwargs)


class MessageDocSearch:
    """Message author.

    Initialized with a list of all messages.
    Find the author’s relative rank and other properties.
    """

    def __init__(self, **kwargs):
        self.search = MessageDoc.search(**kwargs)

    def time_range(self, time):
        """ES Range in time"""
        time_gte = 'now-{}'.format(time)
        return Range(timestamp={'gte': time_gte, 'lt': 'now'})

    def active_members(self, server, time):
        """Number of active users during this period."""
        s = self.search \
            .query(self.time_range(time)) \
            .query(Match(**{'server.id': server.id}))
        return len(set([doc.author.id for doc in s.scan()]))

    def author_lastseen(self, author):
        """Last known date where author has send a message."""
        server = author.server
        s = self.search \
            .query(Match(**{'server.id': server.id})) \
            .query(Match(**{'author.id': author.id})) \
            .sort({'timestamp': {'order': 'desc'}})
        s = s[0]
        for hit in s.execute():
            return hit.timestamp

    def author_rank(self, author, time):
        """Author’s activity rank on a server."""
        s = self.search \
            .query(self.time_range(time)) \
            .query(Match(**{'server.id': author.server.id}))

        author_ids = [doc.author.id for doc in s.scan()]
        counter = Counter(author_ids)
        for rank, (author_id, count) in enumerate(counter.most_common(), 1):
            if author_id == author.id:
                return rank
        return 0

    def author_messages_search(self, author, time):
        """"All of author’s activity on a server."""
        s = self.search \
            .query(self.time_range(time)) \
            .query(Match(**{'server.id': author.server.id})) \
            .query(Match(**{'author.id': author.id}))
        return s

    def author_messages_count(self, author, time):
        """Total of author’s activity on a server."""
        return self.author_messages_search(author, time).count()

    def author_channels(self, author, time):
        """Author’s activity by channel on a server.

        Return as OrderedDict with channel IDs and count.
        """
        s = self.author_messages_search(author, time)
        channel_ids = [doc.to_dict()["channel"]["id"] for doc in s.scan()]
        channels = OrderedDict()
        for channel_id, count in Counter(channel_ids).most_common():
            channels[channel_id] = count
        return channels

    def server_messages(self, server, parser_args):
        """all of server messages."""
        time = parser_args.time
        s = self.search \
            .query(self.time_range(time)) \
            .query(Match(**{'server.id': server.id})) \
            .sort({'timestamp': {'order': 'asc'}})
        return s

    def server_author_messages(self, server, author, parser_args):
        """An author’s messages on a specific server."""
        time = parser_args.time
        s = self.search \
            .query(Match(**{'server.id': server.id})) \
            .query(Match(**{'author.id': author.id})) \
            .query(self.time_range(time)) \
            .sort({'timestamp': {'order': 'asc'}})
        return s


class ESLogger:
    """Elastic Search Logging v2.

    Separated into own class to make migration easier.
    """

    def __init__(self, index_name_fmt=None):
        self.index_name_fmt = index_name_fmt

    @property
    def index_name(self):
        """ES index name.

        Automatically generated using current time.
        """
        now = dt.datetime.utcnow()
        now_str = now.strftime('%Y.%m.%d')
        index_name = self.index_name_fmt.format(now_str)
        return index_name

    @property
    def now(self):
        """Current time"""
        return dt.datetime.utcnow()

    def log_message(self, message):
        """Log message v2."""
        MessageDoc.log(message, index=self.index_name)

    def log_message_delete(self, message):
        """Log deleted message."""
        MessageDeleteDoc.log(message, index=self.index_name)

    @staticmethod
    def parser():
        """Process arguments."""
        # Process arguments
        parser = argparse.ArgumentParser(prog='[p]eslog messagecount')
        # parser.add_argument('key')
        parser.add_argument(
            '-t', '--time',
            default="1d",
            help="Time span in ES notation. 7d for 7 days, 1h for 1 hour"
        )
        parser.add_argument(
            '-c', '--count',
            type=int,
            default="10",
            help='Number of results')
        parser.add_argument(
            '-ec', '--excludechannels',
            nargs='+',
            help='List of channels to exclude'
        )
        parser.add_argument(
            '-ic', '--includechannels',
            nargs='+',
            help='List of channels to exclude'
        )
        parser.add_argument(
            '-eb', '--excludebot',
            action='store_true'
        )
        parser.add_argument(
            '-er', '--excluderoles',
            nargs='+',
            help='List of roles to exclude'
        )
        parser.add_argument(
            '-ir', '--includeroles',
            nargs='+',
            help='List of roles to include'
        )
        parser.add_argument(
            '-ebc', '--excludebotcommands',
            action='store_true'
        )
        parser.add_argument(
            '-s', '--split',
            default='channel',
            choices=['channel']
        )
        return parser

    def search_author_messages(self, author):
        """Search messages by author."""
        s = MessageDoc.search()
        time_gte = 'now-1d'

        s = s.filter('match', **{'author.id': author.id}) \
            .query(Range(timestamp={'gte': time_gte, 'lt': 'now'}))
        for message in s.scan():
            print('-' * 40)
            print(message.to_dict())


class ESLog:
    def __init__(self):
        self.message_search = MessageDocSearch(index="discord-*")

    def eslog_users(self, *args):
        """Message count by users.

        Params:
        --time TIME, -t    
          Time in ES notation. 7d for 7 days, 1h for 1 hour
          Default: 7d (7 days)
        --count COUNT, -c   
          Number of results to show
          Default: 10
        --excludechannels EXCLUDECHANNEL [EXCLUDECHANNEL ...], -ec
          List of channels to exclude
        --includechannels INCLUDECHANNEL [INCLUDECHANNEL ...], -ic
          List of channels to include (multiples are interpreted as OR)
        --excluderoles EXCLUDEROLE [EXCLUDEROLE ...], -er
          List of roles to exclude
        --includeroles INCLUDEROLE [INCLUDEROLE ...], -ir
          List of roles to include (multiples are interpreted as AND)
        --excludebot, -eb
          Exclude bot accounts
        --excludebotcommands, -ebc
          Exclude bot commands. 
        --split {none, channel}, -s
          Split chart

        Example:
        [p]eslog user --time 2d --count 20 --include general some-channel
        Counts number of messages sent by authors within last 2 days in channels #general and #some-channel

        Note:
        It might take a few minutes to process for servers which have many users and activity.
        """

        parser = ESLogger.parser()
        p_args = parser.parse_args(args)


        class Server:
            def __init__(self, id=None, name=None):
                self.id = id
                self.name = name

        server = Server(id='218534373169954816')
        s = self.message_search.server_messages(server, p_args)

        """
        Pandasticsearch
        """
        # for doc in s.scan():
        #     pandas_df = Select.from_dict(doc.to_dict()).to_pandas()
        #     print(pandas_df)

        """
        Create a list of counts over time intervals
        """
        results = [{
            "author_id": doc.author.id,
            "channel_id": doc.channel.id,
            "timestamp": doc.timestamp,
            "rng_index": None,
            "rng_timestamp": None,
            "doc": doc
        } for doc in s.scan()]

        results = sorted(results, key=lambda x: x["timestamp"])
        most_commont_author_ids = Counter([r["doc"].author.id for r in results]).most_common(10)

        now = dt.datetime.utcnow()
        start = results[0]["timestamp"]
        count = 30
        freq = (now - start).total_seconds() / count / 60
        freq = '{}min'.format(int(freq))
        rng = pd.date_range(start=start, end=now, freq=freq)

        for result in results:
            for rng_index, rng_timestamp in enumerate(rng):
                if result["timestamp"] >= rng_timestamp:
                    result["rng_index"] = rng_index
                    result["rng_timestamp"] = rng_timestamp

        message_range = []
        for rng_timestamp in rng:
            messages = []
            for result in results:
                if result["rng_timestamp"] == rng_timestamp:
                    messages.append(result)
            message_range.append(messages)

        for author_id, count in most_commont_author_ids:
            author_message_count = []
            for messages in message_range:
                author_messages = [msg for msg in messages if msg['doc'].author.id == author_id]
                author_message_count.append(len(author_messages))
            for line in sparklines(author_message_count):
                print(author_id)
                print(count)
                print(line)


eslog = ESLog()
eslog.eslog_users()