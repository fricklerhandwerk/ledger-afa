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
import datetime
import ledger
import ledgerparse
import re
import tabulate


# afa relevant account, month and day, decimal seperator
AFA_ACCOUNT = 'ausgaben:job:absetzen:.*wirtschaftsgüter.*'
MONTH = 12
DAY = 31
DEC_SEP = ','

# color coding
WHITE = '\033[97m'
PURPLE = '\033[95m'
BLUE = '\033[94m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
CYAN = '\033[96m'
BOLD = '\033[1m'
DIM = '\033[2m'
GREY = '\033[90m'
UNDERLINE = '\033[4m'
E = '\033[0m'


# functions

def gen_id(transaction, account_name):
    """Generate an ID with the given transaction and account_name."""
    return transaction.code + '-' + transaction.payee + '-' + account_name


class LedgerClass(object):
    """Holds the ledger journal and can query it."""

    def __init__(self, journal):
        """First parameter has to be a ledger journal."""
        self.journal = journal

    def query_to_string(self, query):
        """Output a string with a given query for ledger."""
        out = ledger.Balance()
        for post in self.journal.query(query):
            out += post.amount
        try:
            return str(out.to_amount().to_double()).replace('.', DEC_SEP)
        except Exception:
            return 0.0


class SingleAfaTransaction(object):
    """A single tax reducing afa transaction."""

    def __init__(
        self,
        transaction,
        account_name,
        ledger,
        ledger_query,
        year=datetime.datetime.now().year
    ):
        """Initialize the class object."""
        self.transaction = transaction
        self.account = self.calculate_account(ledger, account_name)
        self.id = gen_id(transaction, account_name)

        self.buy_date = datetime.datetime.now()
        self.calculate_date(ledger)

        self.total_costs = ledgerparse.Money(real_amount=0)
        self.costs_begin = ledgerparse.Money(real_amount=0)
        self.costs_end = ledgerparse.Money(real_amount=0)
        self.calculate_costs(ledger, ledger_query, year)

    def calculate_costs(self, led, ledq, year):
        """
        Calculate the costs for the transaction.

        Get the total costs, costs at the end of the last year
        and the costs at the end of the actual year.
        """
        # get total costs (buy date amount)
        query = '-l "a>0" -p "{}" "{}" and "#{}"'.format(
            self.buy_date.strftime('%Y-%m-%d'),
            self.account,
            self.transaction.code
        )
        self.total_costs = ledgerparse.Money(ledq.query_to_string(query))

        # get costs_begin = amount for that account last year
        query = '-p "to {}-{}-{}" "{}" and "#{}"'.format(
            str(year),
            str(MONTH),
            str(DAY),
            self.account,
            self.transaction.code
        )
        self.costs_begin = ledgerparse.Money(ledq.query_to_string(query))

        # get costs_end = at end of the given year
        query = '-p "to {}" "{}" and "#{}"'.format(
            str(year + 1),
            self.account,
            self.transaction.code
        )
        self.costs_end = ledgerparse.Money(ledq.query_to_string(query))

    def calculate_date(self, ledger_journal):
        """Find buy date."""
        # FIXME: Find the minimum date for the transaction with the same
        #        transaction code. This is probably not very robust.
        self.buy_date = min(
            t.aux_date for t in ledger_journal
            if t.code == self.transaction.code
        )

    def calculate_account(self, led, otherwise):
        """Get the account name of the inventory account."""
        # check which account of the transactions is < 0
        for y, acc in enumerate(self.transaction.accounts):
            if self.transaction.balance_account(y) < ledgerparse.Money('0'):
                return self.transaction.accounts[y].name

        # change nothing otherwise
        return otherwise

    def costs_diff(self):
        """Calculate the difference between costs_beginn and costs_end."""
        return self.costs_begin - self.costs_end

    def __str__(self):
        """Return a string of the object."""
        return '{} ({}={})'.format(
            self.transaction.payee,
            self.date_this_year.strftime('%Y-%m-%d'),
            self.buy_date.strftime('%Y-%m-%d')
        )


class AfaTransactions(object):
    """Holds all AfaTransaction-Objects."""

    def __init__(self, ledgerparse, ledgerclass):
        """Initialize the class."""
        self.ledgerparse = ledgerparse
        self.ledgerclass = ledgerclass
        self.transactions = self.get_afa_accounts()

    def get_afa_accounts(self):
        """Search all transactions, which are afa compliant."""
        # FIXME: Refactor this to make it readable.
        out = []
        for trans in self.ledgerparse:
            # get only transactions done this year (aux date of afa trans!)
            if trans.aux_date == datetime.datetime(ARGUMENTS.year, MONTH, DAY):
                # ... and those who HAVE a code
                if len(trans.code) > 0:
                    # ... and which names have afa account in it
                    for i, acc in enumerate(trans.accounts):
                        if re.match(
                                ARGUMENTS.account,
                                acc.name,
                                re.IGNORECASE
                        ):
                            # ... and only accounts which have amount > 0
                            # on YEAR-MONTH-DAY
                            if trans.balance_account(i).amount > 0:
                                # and only if this does not already exists
                                if (gen_id(trans, acc.name) not in
                                        [t.id for t in out]):
                                    out.append(
                                        SingleAfaTransaction(
                                            trans,
                                            acc.name,
                                            self.ledgerparse,
                                            self.ledgerclass,
                                            ARGUMENTS.year
                                        )
                                    )
        return out

    def add_table_entry(
        self,
        date='',
        code='',
        item='',
        account='',
        costs='',
        costs_begin='',
        costs_diff='',
        costs_end=''
    ):
        """Output two tabulate compliant table lines."""
        line_a = [
            unicode(date, 'utf-8'),
            YELLOW + unicode(code, 'utf-8') + E,
            BOLD + unicode(item, 'utf-8') + E,
            RED + unicode(costs, 'utf-8') + E,
            WHITE + unicode(costs_begin, 'utf-8') + E,
            CYAN + unicode(costs_diff, 'utf-8') + E,
            WHITE + unicode(costs_end, 'utf-8') + E
        ]
        line_b = [
            '',
            '',
            PURPLE + unicode('   ' + account, 'utf-8') + E,
            '',
            '',
            '',
            ''
        ]
        return [line_a, line_b]

    def output(self):
        """Print the afa transactions on the output."""
        # init the header for the table
        header = [
            UNDERLINE + BOLD + BLUE + 'Kaufdatum',
            'Beleg-Nr.',
            unicode('Gerät + Konto', 'utf-8'),
            'Kaufpreis',
            'Buchwert Anfang',
            'Buchwert Diff',
            'Buchwert Ende' + E
        ]

        # init the table
        table = [header]

        # init the variables for the output
        sum_costs = ledgerparse.Money('0')
        sum_begin = ledgerparse.Money('0')
        sum_diff = ledgerparse.Money('0')
        sum_end = ledgerparse.Money('0')

        # get variables from transaction list
        for x in sorted(self.transactions, key=lambda y: y.buy_date):
            table.extend(self.add_table_entry(
                str(x.buy_date.strftime('%Y-%m-%d')),
                x.transaction.code,
                x.transaction.payee,
                str(x.account),
                str(x.total_costs),
                str(x.costs_begin),
                str(x.costs_diff()),
                str(x.costs_end))
            )
            sum_costs += x.total_costs
            sum_begin += x.costs_begin
            sum_diff += x.costs_diff()
            sum_end += x.costs_end

        table.extend(self.add_table_entry())
        table.extend(self.add_table_entry(
            item='Summen:',
            costs=str(sum_costs),
            costs_begin=str(sum_begin),
            costs_diff=str(sum_diff),
            costs_end=str(sum_end))
        )

        print(tabulate.tabulate(table, tablefmt='plain'))


def main():
    # set up the arguments
    ap = argparse.ArgumentParser(
        description='Programm for calculating and summing up tax reduction'
        ' inventory purchases.'
    )

    ap.add_argument(
        'file',
        help='a ledger journal'
    )
    ap.add_argument(
        '-y',
        '--year',
        type=int,
        default=datetime.datetime.now().year,
        help='year for calculation'
    )
    ap.add_argument(
        '-a',
        '--account',
        default=AFA_ACCOUNT,
        help='afa account'
    )

    ARGUMENTS = ap.parse_args()

    # get ledger journal into the afa transactions class
    AFA = AfaTransactions(
        ledgerparse.string_to_ledger(
            ledgerparse.ledger_file_to_string(ARGUMENTS.file),
            True
        ),
        LedgerClass(
            ledger.read_journal(ARGUMENTS.file)
        )
    )

    # get spicy output, baby!
    AFA.output()

if __name__ == '__main__':
    main()
