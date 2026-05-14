import re

sql1 = """SELECT * FROM t WHERE col = 'with'
LIMIT 100"""

sql2 = """SELECT * FROM t WHERE col = 'with'
LIMIT 100;"""

regex = r'(?i)\s+LIMIT\s+\d+\s*$'

print("SQL1 stripped:")
print(repr(re.sub(regex, '', sql1)))

print("SQL2 stripped (with manual rstrip):")
print(repr(re.sub(regex, '', sql2.rstrip(";"))))
