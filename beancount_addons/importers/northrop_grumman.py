from beancount.core.number import D
from beancount.ingest import importer
from beancount.core import account
from beancount.core import amount
from beancount.core import flags
from beancount.core import data
from beancount.core.position import Cost

from dateutil.parser import parse

from titlecase import titlecase

import csv
import os
import re


class NGPayStubImporter(importer.ImporterProtocol):
    def __init__(self, account, lastfour):
        self.account = account
        self.lastfour = lastfour

    def identify(self, f):
        return re.match(
            r"Chase{}.*\.CSV".format(self.lastfour), os.path.basename(f.name)
        )

    def file_account(self, f):
        return self.account

    def file_date(self, f):
        match = re.match(
            r"Chase\d{4}_Activity\d{8}_(\d{8})_\d{8}.CSV",
            os.path.basename(f.name),
            re.IGNORECASE,
        )

        if match is not None:
            return parse(match.group(1)).date()

    def file_name(self, f):
        return f"Chase{self.lastfour}.csv"

    def extract(self, f):
        entries = []

        with open(f.name) as f:
            for index, row in enumerate(csv.DictReader(f)):
                trans_date = parse(row["Transaction Date"]).date()
                trans_desc = titlecase(row["Description"])
                trans_amt = row["Amount"]

                meta = data.new_metadata(f.name, index)

                meta["original-description"] = trans_desc

                txn = data.Transaction(
                    meta=meta,
                    date=trans_date,
                    flag=flags.FLAG_OKAY,
                    payee=trans_desc,
                    narration="",
                    tags=set(),
                    links=set(),
                    postings=[],
                )

                txn.postings.append(
                    data.Posting(
                        self.account,
                        amount.Amount(D(trans_amt), "USD"),
                        None,
                        None,
                        None,
                        None,
                    )
                )

                entries.append(txn)

        return entries
