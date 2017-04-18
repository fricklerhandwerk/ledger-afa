# coding=utf-8

"""
A program for calculating and displaying tax deprecation on specified items
in a ledger journal.

This script will only work, if there are only TWO accounts in the afa
transaction at the end of a ARGUMENTS.year: the one which will apply to the
tax reduction afa list and the one from which it comes (inventory of the
business). Example:

2016-12-31 * (a99) New NTG3 microphone
  afa-tax-reduction:Microphones  $ 100,00
  inventory:NTG3 microphone
"""

import argparse
import colorama
import ledger
import re
import tabulate

from datetime import date
from termcolor import colored


AFA_ACCOUNT = 'AfA'
MONTH = 12
DAY = 31


def get_sub_accounts(account):
    top = [a for a in account.accounts()]
    sub = [a for acc in account.accounts() for a in get_sub_accounts(acc)]
    return top + sub


def get_afa_posts(journal, account, year):
    """
    get all postings that went to afa accounts this year.

    this way we can trace back inventory items which are being deprecated.
    """
    top = journal.find_account(account)
    accounts = [top] + get_sub_accounts(top)

    return [p for a in accounts for p in a.posts()
            if p.date.year == year]


def get_inventory(posts):
    """
    get accounts for inventory items which are being deprecated.

    this is done looking at each deprecation post and taking all
    other accounts in the transaction of that post.
    """

    # monkey patch so we can use `Account` in `set`
    ledger.Account.__hash__ = lambda self: hash(self.fullname())

    inventory = set()
    for post in posts:
        # other accounts from the parent transaction of this posting
        inventory |= set(p.account for p in post.xact.posts()
                         if p.account.fullname() != post.account.fullname())

    return inventory


def table_entry(
    date='',
    code='',
    item='',
    initial_value='',
    last_year_value='',
    deprecation_amount='',
    next_year_value=''
):
    return [
        date,
        colored(code, 'yellow'),
        item,
        colored(str(initial_value), 'red'),
        str(last_year_value),
        colored(str(deprecation_amount), 'cyan'),
        str(next_year_value),
    ]


def create_table(items):
    colorama.init()  # needed only for windows terminal color support

    def color_header(s):
        return colored(s, attrs=['bold'])

    def color_footer(s):
        return colored(s, attrs=['bold'])

    header = [
        'Kaufdatum',
        'Beleg',
        'Gerät',
        'Kaufpreis',
        'Buchwert Anfang',
        'Abschreibung',
        'Buchwert Ende',
    ]

    table = [map(color_header, header)]

    sum_initial_value = sum(i.initial_value for i in items)
    sum_last_year_value = sum(i.last_year_value for i in items)
    sum_deprecation_amount = sum(i.deprecation_amount for i in items)
    sum_next_year_value = sum(i.next_year_value for i in items)

    for x in sorted(items, key=lambda y: y.buy_date):
        line = table_entry(
            x.buy_date.isoformat(),
            x.code,
            x.item,
            x.initial_value,
            x.last_year_value,
            x.deprecation_amount,
            x.next_year_value,
        )
        table.append(line)

    footer = table_entry(
        item='Gesamt',
        initial_value=sum_initial_value,
        last_year_value=sum_last_year_value,
        deprecation_amount=sum_deprecation_amount,
        next_year_value=sum_next_year_value,
    )

    table.append(map(color_footer, footer))

    table = [map(lambda s: s.decode('utf-8'), row) for row in table]

    return table


class LedgerClass(object):
    """Holds the ledger journal and can query it."""

    def __init__(self, journal):
        """First parameter has to be a ledger journal."""
        self.journal = journal

    def query_total(self, query):
        """Compute total of queried posts"""
        return sum(post.amount for post in self.journal.query(query))


class SingleAfaTransaction(object):
    """A single tax reducing afa transaction."""

    def __init__(
        self,
        transaction,
        account_name,
        journal,
        year=date.today().year
    ):
        """Initialize the class object."""
        self.transaction = transaction
        self.account = self.calculate_account(account_name)

        self.buy_date = date.today()
        self.calculate_date(journal)

        self.total_costs = ledger.Amount(0)
        self.last_year_value = ledger.Amount(0)
        self.next_year_value = ledger.Amount(0)
        self.calculate_costs(journal, year)

    def calculate_costs(self, journal, year):
        """
        Calculate the costs for the transaction.

        Get the total costs, costs at the end of the last year
        and the costs at the end of the current year.
        """
        # get total costs (buy date amount)
        query = '-l "a>0" -p "{}" "{}" and "#{}" and @"{}"'.format(
            self.buy_date.isoformat(),
            self.account,
            self.transaction.code,
            self.transaction.payee,
        )
        self.total_costs = journal.query_total(query)

        # get last_year_value = amount for that account last year
        query = '-p "to {}-{}-{}" "{}" and "#{}" and @"{}"'.format(
            str(year),
            str(MONTH),
            str(DAY),
            self.account,
            self.transaction.code,
            self.transaction.payee,
        )
        self.last_year_value = journal.query_total(query)

        # get next_year_value = at end of the given year
        query = '-p "to {}" "{}" and "#{}" and @"{}"'.format(
            str(year + 1),
            self.account,
            self.transaction.code,
            self.transaction.payee,
        )
        self.next_year_value = journal.query_total(query)

    def calculate_date(self, journal):
        """Find buy date."""
        # FIXME: Find the minimum date for the transaction with the same
        #        transaction code. This is probably not very robust.
        transactions = journal.journal.xacts()
        self.buy_date = min(t.date for t in transactions
                            if t.code == self.transaction.code)

    def calculate_account(self, default):
        """Get the account name of the inventory account."""
        # the inventory account is distinguished by negative balance
        for post in self.transaction.posts():
            if post.amount < 0:
                return post.account.fullname()

        return default

    def deprecation_amount(self):
        """Calculate the difference between last_year_valuen and next_year_value."""
        return self.last_year_value - self.next_year_value

    def __str__(self):
        """Return a string of the object."""
        return '{} ({}={})'.format(
            self.transaction.payee,
            self.buy_date.isoformat()
        )


class InventoryItem(object):
    def __init__(self, account, year):
        self.item = account.name
        self.account = account.fullname()
        self.year = year

        first_post = account.posts().next()
        self.code = first_post.xact.code
        self.buy_date = first_post.date
        self.initial_value = first_post.amount

        self.last_year_value = sum(p.amount for p in account.posts()
                                   if p.date.year < year)
        self.next_year_value = sum(p.amount for p in account.posts()
                                   if p.date.year <= year)
        self.deprecation_amount = sum(p.amount for p in account.posts()
                                      if p.date.year == year)


class AfaTransactions(object):
    """Holds all AfaTransaction-Objects."""

    def __init__(self, journal, account, year):
        """Initialize the class."""
        self.journal = journal
        self.account = account
        self.year = year
        self.transactions = self.get_afa_accounts()

        self.actual_journal = journal.journal
        self.posts = self.get_afa_posts(account, year)
        self.inventory = self.get_inventory_accounts(self.posts)
        self.items = [InventoryItem(i, self.year) for i in self.inventory]

    def get_afa_accounts(self):
        """Search all transactions, which are afa compliant."""
        # FIXME: Refactor this to make it readable.
        out = []
        transactions = self.journal.journal.xacts()
        for trans in transactions:
            # get transactions done this year (aux date of afa trans!)
            # and those who HAVE a code
            this_year = date(self.year, MONTH, DAY)
            if trans.date == this_year and trans.code:
                for post in trans.posts():
                    name = post.account.fullname()

                    matches = re.match(self.account, name, re.IGNORECASE)
                    amount_positive = post.amount > 0
                    exists = trans.code + trans.payee in [t.transaction.code + t.transaction.payee for t in out]

                    if matches and amount_positive and not exists:
                        tx = SingleAfaTransaction(
                            trans,
                            name,
                            self.journal,
                            self.year,
                        )
                        out.append(tx)
        return out


def main():
    args = argparse.ArgumentParser(
        description=('A program for calculating and displaying tax deprecation '
                     'on specified items in a ledger journal.')
    )
    args.add_argument(
        'file',
        help='a ledger journal'
    )
    args.add_argument(
        '-y',
        '--year',
        type=int,
        default=date.today().year,
        help='year for calculation'
    )
    args.add_argument(
        '-a',
        '--account',
        default=AFA_ACCOUNT,
        help='afa account'
    )

    args = args.parse_args()

    journal = ledger.read_journal(args.file)
    posts = get_afa_posts(journal, args.account, args.year)
    inventory = [InventoryItem(i, args.year) for i in get_inventory(posts)]
    table = create_table(inventory)

    print(tabulate.tabulate(table, tablefmt='plain'))

if __name__ == '__main__':
    main()
