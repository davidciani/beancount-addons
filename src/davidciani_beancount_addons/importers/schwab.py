# SPDX-FileCopyrightText: 2025-present David Ciani <dciani@davidciani.com>
#
# SPDX-License-Identifier: MIT
"""Importers for Charles Schwab JSON transaction files."""

import json
import re
from datetime import date, datetime
from pathlib import Path

import beangulp
from beancount.core import amount, data, flags
from beancount.core.number import D
from beangulp import mimetypes

from davidciani_beancount_addons import time_zone
from davidciani_beancount_addons.importers import BalanceType


class CheckingImporter(beangulp.Importer):
    """An importer Charles Schwab Checking account JSON transaction files."""

    def __init__(
        self,
        acctid_regexp: str,
        account: str,
        basename: str | None = None,
        balance_type: BalanceType = BalanceType.DECLARED,
    ) -> None:
        """Create a new importer posting to the given account.

        Args:
          account: An account string, the account onto which to post all the
            amounts parsed.
          acctid_regexp: A regexp, to match against the <ACCTID> tag of the OFX file.
          basename: An optional string, the name of the new files.
          balance_type: An enum of type BalanceType.
        """
        self.acctid_regexp = acctid_regexp
        self.importer_account = account
        self.basename = basename
        self.balance_type = balance_type

    def identify(self, filepath: str) -> bool:
        """Match for a compatible MIME type and account ID.

        The only way to identify Schwab files is by the partialy redacted
        account number in the file path. Filepath format has changed over time.
        """
        if mimetypes.guess_file_type(filepath, strict=False)[0] not in {
            "application/json",
        }:
            return False

        filepath_stem = Path(filepath).stem

        if "checking_transactions" not in filepath_stem.lower():
            return False

        return bool(re.match(self.acctid_regexp, filepath_stem))

    def account(self, filepath: str) -> data.Account:  # noqa: ARG002
        """Return the account against which we post transactions."""
        return self.importer_account

    def date(self, filepath: str) -> date | None:
        """Return the optional renamed account filename."""
        contents = json.loads(Path(filepath).read_text())
        return (
            datetime.strptime(contents["ToDate"], "%m/%d/%Y")
            .astimezone(time_zone)
            .date()
        )

    def filename(self, filepath: str) -> str | None:
        """Return the optional renamed account filename."""
        if self.basename:
            return self.basename + Path(filepath).suffix
        return None

    def extract(self, filepath: str, existing: data.Entries) -> data.Directives:  # noqa: ARG002
        """Extract a list of partially complete transactions from the file."""
        contents = json.loads(Path(filepath).read_text())

        new_entries = []
        for transaction in contents["PostedTransactions"]:
            # Basic transaction details
            date = (
                datetime.strptime(transaction["Date"], "%m/%d/%Y")
                .astimezone(time_zone)
                .date()
            )
            narration = transaction["Description"]

            # Build metadata dictionary
            metadata_dict = data.new_metadata("<build_transaction>", 0)
            metadata_dict["transaction_type"] = transaction["Type"]
            if (
                transaction["CheckNumber"] is not None
                and transaction["CheckNumber"] != ""
            ):
                metadata_dict["check_number"] = transaction["CheckNumber"]

            # transaction amount (skip first char, dollar sign)
            if transaction["Withdrawal"] != "":
                number = D(transaction["Withdrawal"][1:]) * D("-1")
            else:
                number = D(transaction["Deposit"][1:])

            units = amount.Amount(number, "USD")  # always USD

            # Create a single leg transaction. User to complete manualy.
            posting = data.Posting(self.importer_account, units, None, None, None, None)

            # Return preped transaction
            new_entries.append(
                data.Transaction(
                    metadata_dict,
                    date,
                    flags.FLAG_OKAY,
                    None,  # no payee
                    narration,
                    data.EMPTY_SET,
                    data.EMPTY_SET,
                    [posting],
                ),
            )

        return data.sorted(new_entries)
