# SPDX-FileCopyrightText: 2025-present David Ciani <dciani@davidciani.com>
#
# SPDX-License-Identifier: MIT
"""OFX file format importer for bank and credit card statements.

https://en.wikipedia.org/wiki/Open_Financial_Exchange

"""

import datetime
import itertools
import re
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any
from xml.sax import saxutils

import beangulp
from beancount.core import amount, data, flags
from beancount.core.number import D
from beangulp import mimetypes
from bs4 import BeautifulSoup
from bs4.element import NavigableString, PageElement, Tag
 
from davidciani_beancount_addons.importers import BalanceType


class Importer(beangulp.Importer):
    """An importer for Open Financial Exchange files."""

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
        """Match for a compatible MIME type and account ID."""
        if mimetypes.guess_type(filepath, strict=False)[0] not in {
            "application/x-ofx",
            "application/vnd.intu.qbo",
            "application/vnd.intu.qfx",
        }:
            return False

        contents = Path(filepath).read_text()

        return any(
            re.match(self.acctid_regexp, acctid) for acctid in find_acctids(contents)
        )

    def account(self, filepath: str) -> data.Account:  # noqa: ARG002
        """Return the account against which we post transactions."""
        return self.importer_account

    def date(self, filepath: str) -> datetime.date | None:
        """Return the optional renamed account filename."""
        contents = Path(filepath).read_text()
        return find_max_date(contents)

    def filename(self, filepath: str) -> str | None:
        """Return the optional renamed account filename."""
        if self.basename:
            return self.basename + Path(filepath).suffix
        return None

    def extract(self, filepath: str, existing: data.Entries) -> data.Entries:  # noqa: ARG002
        """Extract a list of partially complete transactions from the file."""
        soup = BeautifulSoup(Path(filepath).read_text(), "lxml")
        return extract(
            soup,
            filepath,
            self.acctid_regexp,
            self.importer_account,
            flags.FLAG_OKAY,
            self.balance_type,
        )


def extract(  # noqa: PLR0913
    soup: BeautifulSoup,
    filename: str,
    acctid_regexp: str,
    account: str,
    flag: str,
    balance_type: BalanceType,
) -> data.Entries:
    """Extract transactions from an OFX file.

    Args:
      soup: A BeautifulSoup root node.
      acctid_regexp: A regular expression string matching the account we're
        interested in.
      account: An account string onto which to post the amounts found in the file.
      flag: A single-character string.
      balance_type: An enum of type BalanceType.

    Returns:
      A sorted list of entries.
    """
    new_entries = []
    counter = itertools.count()
    for acctid, currency, transactions, balance in find_statement_transactions(soup):
        if not re.match(acctid_regexp, acctid):
            continue

        # Create Transaction directives.
        stmt_entries = []
        for stmttrn in transactions:
            if isinstance(stmttrn, Tag):
                entry = build_transaction(stmttrn, flag, account, currency)
                entry = entry._replace(meta=data.new_metadata(filename, next(counter)))
                stmt_entries.append(entry)
        stmt_entries = data.sorted(stmt_entries)
        new_entries.extend(stmt_entries)

        # Create a Balance directive.
        if balance and balance_type is not BalanceType.NONE:
            date, number = balance
            if balance_type is BalanceType.LAST and stmt_entries:
                date = stmt_entries[-1].date

            # The Balance assertion occurs at the beginning of the date, so move
            # it to the following day.
            date += datetime.timedelta(days=1)

            meta = data.new_metadata(filename, next(counter))
            balance_entry = data.Balance(
                meta,
                date,
                account,
                amount.Amount(number, currency),
                None,
                None,
            )  # type: ignore
            new_entries.append(balance_entry)

    return data.sorted(new_entries)


def parse_ofx_time(date_str: str | None) -> datetime.datetime | None:
    """Parse an OFX time string and return a datetime object.

    Args:
      date_str: A string, the date to be parsed.

    Returns:
      A datetime.datetime instance.
    """
    if date_str is None:
        return None
    if len(date_str) < 14:
        return datetime.datetime.strptime(date_str[:8], "%Y%m%d")
    return datetime.datetime.strptime(date_str[:14], "%Y%m%d%H%M%S")


def find_acctids(contents: str) -> Generator[str]:
    """Find the list of <ACCTID> tags.

    Args:
      contents: A string, the contents of the OFX file.

    Returns:
      A list of strings, the contents of the <ACCTID> tags.
    """
    # Match the account id. Don't bother parsing the entire thing as XML, just
    # match the tag for this purpose. This'll work fine enough.
    for match in re.finditer("<ACCTID>([^<]*)", contents):
        yield match.group(1)


def find_max_date(contents: str) -> datetime.datetime | None:
    """Extract the report date from the file."""
    soup = BeautifulSoup(contents, "lxml")
    dates = []
    for ledgerbal in soup.find_all("ledgerbal"):
        if not isinstance(ledgerbal, Tag):
            continue
        dtasof = ledgerbal.find("dtasof")
        if isinstance(dtasof, Tag) and isinstance(
            dtasof.contents[0],
            NavigableString,
        ):
            parsed_datetime = parse_ofx_time(dtasof.contents[0])
            if parsed_datetime is not None:
                dates.append(parsed_datetime.date())
    if dates:
        return max(dates)
    return None


def find_currency(soup: BeautifulSoup) -> str | None:
    """Find the first currency in the XML tree.

    Args:
      soup: A BeautifulSoup root node.

    Returns:
      A string, the first currency found in the file. Returns None if no currency
      is found.
    """
    for stmtrs in soup.find_all(re.compile(".*stmtrs$")):
        if not isinstance(stmtrs, Tag):
            continue
        for currency_node in stmtrs.find_all("curdef"):
            if isinstance(currency_node, Tag) and isinstance(
                currency_node.contents[0],
                NavigableString,
            ):
                currency = currency_node.contents[0]
                if currency is not None:
                    return currency
    return None


def find_statement_transactions(
    soup: BeautifulSoup,
) -> Generator[tuple[str, str, list[PageElement], tuple[datetime.date, Any] | None]]:
    """Find the statement transaction sections in the file.

    Args:
      soup: A BeautifulSoup root node.

    Yields:
      A trip of
        An account id string,
        A currency string,
        A list of transaction nodes (<STMTTRN> BeautifulSoup tags), and
        A (date, balance amount) for the <LEDGERBAL>.
    """
    # Process STMTTRNRS and CCSTMTTRNRS tags.
    for stmtrs in soup.find_all(re.compile(".*stmtrs$")):
        if not isinstance(stmtrs, Tag):
            continue

        # For each CURDEF tag.
        for currency_node in stmtrs.find_all("curdef"):
            if isinstance(currency_node, Tag) and isinstance(
                currency_node.contents[0],
                NavigableString,
            ):
                currency = currency_node.contents[0].strip()
            else:
                currency = ""

            # Extract ACCTID account information.
            acctid_node = stmtrs.find("acctid")
            if isinstance(acctid_node, Tag):
                acctid_node_child = next(acctid_node.children)
                if isinstance(
                    acctid_node_child,
                    NavigableString,
                ):
                    acctid = acctid_node_child.strip()
                else:
                    acctid = ""
            else:
                acctid = ""

            # Get the LEDGERBAL node. There appears to be a single one for all
            # transaction lists.
            ledgerbal = stmtrs.find("ledgerbal")
            balance = None
            if isinstance(ledgerbal, Tag):
                dtasof = find_child(ledgerbal, "dtasof", parse_ofx_time).date()
                balamt = find_child(ledgerbal, "balamt", D)
                balance = (dtasof, balamt)

            # Process transaction lists (regular or credit-card).
            for tranlist in stmtrs.find_all(re.compile("(|bank|cc)tranlist")):
                if isinstance(tranlist, Tag):
                    yield acctid, currency, tranlist.find_all("stmttrn"), balance


def find_child[T](
    node: Tag,
    name: str,
    conversion: Callable[[Any], T] | None = None,
) -> T | str | None:
    """Find a child under the given node and return its value.

    Args:
      node: A <STMTTRN> bs4.element.Tag.
      name: A string, the name of the child node.
      conversion: A callable object used to convert the value to a new data type.

    Returns:
      A string, or None.
    """
    child = node.find(name)
    if not child:
        return None
    if isinstance(child, Tag) and isinstance(child.contents[0], NavigableString):
        value = child.contents[0].strip()
    else:
        value = None
    if conversion:
        value = conversion(value)
    return value


def build_transaction(
    stmttrn: Tag,
    flag: str,
    account: str,
    currency: str,
) -> data.Transaction:
    """Build a single transaction.

    Args:
      stmttrn: A <STMTTRN> bs4.element.Tag.
      flag: A single-character string.
      account: An account string, the account to insert.
      currency: A currency string.

    Returns:
      A Transaction instance.
    """
    # Find the date.
    date = parse_ofx_time(find_child(stmttrn, "dtposted")).date()

    # There's no distinct payee.
    payee = None

    # Construct a description that represents all the text content in the node.
    name = find_child(stmttrn, "name", saxutils.unescape)
    memo = find_child(stmttrn, "memo", saxutils.unescape)

    # Remove memos duplicated from the name.
    if memo == name:
        memo = None

    # Add the transaction type to the description, unless it's not useful.
    trntype = find_child(stmttrn, "trntype", saxutils.unescape)
    if trntype in ("DEBIT", "CREDIT"):
        trntype = None

    narration = " / ".join(filter(None, [name, memo, trntype]))

    # Create a single posting for it; the user will have to manually categorize
    # the other side.
    number = find_child(stmttrn, "trnamt", D)
    units = amount.Amount(number, currency)
    posting = data.Posting(account, units, None, None, None, None)

    # Build the transaction with a single leg.
    fileloc = data.new_metadata("<build_transaction>", 0)
    return data.Transaction(
        fileloc,
        date,
        flag,
        payee,
        narration,
        data.EMPTY_SET,
        data.EMPTY_SET,
        [posting],
    )  # type: ignore
