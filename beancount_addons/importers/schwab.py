#!/usr/bin/env python3

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


class SchwabBankImporter(importer.ImporterProtocol):
    def __init__(self, account, lastfour):
        self.account = account
        self.lastfour = lastfour

    def identify(self, f):
        return re.match(
            r'XXXXXX.*{}_Checking_Transactions_.*\.CSV'.format(
                self.lastfour), os.path.basename(
                f.name))

    def file_account(self, f):
        return self.account
    
    def file_date(self, f):
        with open(f.name) as fh:
            line = fh.readline()

        match = re.search(r'to (.{10})',
                         line,
                         re.IGNORECASE)
        
        if match is not None:
            return parse(match.group(1)).date()
        
    def file_name(self, f):
        return f'SchwabBank{self.lastfour}.csv'

    def extract(self, f):
        entries = []

        with open(f.name) as f:
            while True:  # first 3 lines are garbage
                if re.search('Posted Transactions', next(f)) is not None:
                    break

            for index, row in enumerate(csv.reader(f)):
                trans_date = parse(row[0]).date()
                trans_desc = titlecase(row[3])

                if row[4]:
                    trans_amt = amount.Amount(D(row[4].strip('$')) * -1, 'USD')
                elif row[5]:
                    trans_amt = amount.Amount(D(row[5].strip('$')), 'USD')
                else:
                    continue  # 0 dollar transaction

                meta = data.new_metadata(f.name, index)

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
                        trans_amt,
                        None,
                        None,
                        None,
                        None))

                entries.append(txn)

        return entries
