import re
from pprint import pprint
from collections import defaultdict
from itertools import tee
from datetime import date
from tika import parser
import pandas as pd


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


file_path = "/Users/davidciani/Downloads/pay-stubs/2021-02.pdf"
file_data = parser.from_file(file_path)
text = file_data["content"]


## Process Key-Values

paystub_info = {
    "Name": None,
    "My ID": None,
    "Badge": None,
    "Cost Center": None,
    "SubArea": None,
    "EE Grp": None,
    "EE SGrp": None,
    "Pay Date": None,
    "Pay Period": None,
    "Hours worked": None,
}

for a, b in pairwise(re.split("\s{2,}", text)):
    if a[0:-1] in paystub_info.keys():
        paystub_info[a[0:-1]] = b

# cleanup pay period

m = re.match(
    "(\d{2})/(\d{2})/(\d{4})- (\d{2})/(\d{2})/(\d{4}) Period No: (\d{2})/(\d{4})",
    paystub_info["Pay Period"],
)

del paystub_info["Pay Period"]

paystub_info["Pay Period Start"] = date(int(m[3]), int(m[1]), int(2))
paystub_info["Pay Period End"] = date(int(m[6]), int(m[4]), int(5))
paystub_info["Pay Period Year"] = int(m[8])
paystub_info["Pay Period Number"] = int(m[7])


pprint(paystub_info)

paystub_info_s = pd.Series(
    paystub_info.values(), index=paystub_info.keys(), name="paystub_info"
)

print(paystub_info_s)
print()

## Process Tables
table_sections = [
    "Earnings",
    "Deductions",
    "Taxes",
    "Other Benefits & Information",
    "Quota Information",
    "Distribution of Net Payment",
]

current_table = None
tables = defaultdict(list)

for line in text.splitlines():
    # Parse line and skip if blank
    stripped_line = line.strip()

    if stripped_line == "":
        current_table = None
        continue

    split_line = re.split("\s{2,}", stripped_line)

    # Detect section boundaries
    if stripped_line in table_sections:
        table_name = re.sub("\W+", "_", stripped_line.lower())
        current_table = table_name
        continue

    # Add record to table
    if current_table is not None:
        tables[current_table].append(split_line)

# cleanup the taxes table
for ix, row in enumerate(tables["taxes"][1:]):
    tables["taxes"][ix + 1] = [" ".join(row[0:2])] + row[2:]

# leanup the earnings table
tables["earnings"][0] = ["DESCRIPTION", "CURRENT", "YEAR-TO-DATE", "RETRO DATE"]

# cleanup the deductions table
tables["deductions"][0] = ["DESCRIPTION", "CURRENT", "REMARK", "YEAR-TO-DATE"]
for ix, row in enumerate(tables["deductions"][1:]):
    if len(row) == 3:
        tables["deductions"][ix + 1] = row[0:2] + [""] + row[2:]

# cleanup table record lengths
for key, table in tables.items():

    record_length = len(table[0])
    for ix, row in enumerate(table[1:]):
        table[ix + 1] = row + [""] * (record_length - len(row))

tables_df = {}

for key, table in tables.items():
    tables_df[key] = pd.DataFrame(table[1:], columns=table[0])
    tables_df[key].name = key

pprint(tables)


for table in tables_df.values():
    print(table)
    print()
