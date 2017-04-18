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
import tabulate

from datetime import date
from termcolor import colored


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


def main():
    args = argparse.ArgumentParser(
        description=('A program for calculating and displaying tax deprecation '
                     'on specified items in a ledger journal.')
    )
    args.add_argument(
        'file',
        help='ledger journal'
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
        default='AfA',
        help='account for deprecation'
    )

    args = args.parse_args()

    journal = ledger.read_journal(args.file)
    posts = get_afa_posts(journal, args.account, args.year)
    inventory = [InventoryItem(i, args.year) for i in get_inventory(posts)]
    table = create_table(inventory)

    print(tabulate.tabulate(table, tablefmt='plain'))

if __name__ == '__main__':
    main()
