from pandasticsearch import DataFrame
df = DataFrame.from_es(url='http://localhost:9200', index='discord-2017.07.26')

# print schema of index
df.print_schema()

# inspect columns
# print(df.columns)

# print(df.author)

for row in df.collect():
    print(row['server'])


# df['author_name'] = df['author'].apply(lambda x: x['properties']['display_name'])
# print(df)

# Projection
# df.filter(df.author['properties']['display_name'] == 'SML').select('author', 'channel', 'server', 'timestamp')

