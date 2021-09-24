from datetime import date
from beancount.core.number import D
from beancount.ingest import importer
from beancount.core import account
from beancount.core import amount
from beancount.core import flags
from beancount.core import data
from beancount.core.position import Cost

from dateutil.parser import parse

from titlecase import titlecase

import sys

import csv
import os
import re


class AppleCardImporter(importer.ImporterProtocol):
    def __init__(self, account):
        self.account = account

    def identify(self, f):
        return re.match(r"Apple Card Transactions.+", os.path.basename(f.name))

    def file_account(self, f):
        return self.account

    def file_date(self, f):
        match = re.match(
            r"Apple Card Transactions - (\w+) (\d{4}).csv",
            os.path.basename(f.name),
            re.IGNORECASE,
        )

        if match is not None:
            return parse(
                f"{match.group(2)}-{match.group(1)}", default=date(2021, 1, 31)
            )

    def file_name(self, f):
        return f"AppleCard.csv"

    def extract(self, f):
        entries = []

        with open(f.name) as f:
            for index, row in enumerate(csv.DictReader(f)):
                trans_date = parse(row["Transaction Date"]).date()
                trans_payee = titlecase(row["Merchant"])
                trans_desc = titlecase(row["Description"])
                trans_amt = row["Amount (USD)"]
                trans_type = row["Type"]

                meta = data.new_metadata(f.name, index)

                meta["original-description"] = f"{trans_payee}"

                txn = data.Transaction(
                    meta=meta,
                    date=trans_date,
                    flag=flags.FLAG_OKAY,
                    payee=trans_payee,
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

                if trans_type == "Installment":
                    txn.postings.append(
                        data.Posting(
                            f"{self.account}:Installments",
                            amount.Amount(-D(trans_amt), "USD"),
                            None,
                            None,
                            None,
                            None,
                        )
                    )
                elif trans_type == "Payment":
                    txn.postings.append(
                        data.Posting(
                            f"Equity:TransferSuspense",
                            amount.Amount(-D(trans_amt), "USD"),
                            None,
                            None,
                            None,
                            None,
                        )
                    )

                entries.append(txn)

        return entries
