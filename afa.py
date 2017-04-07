# coding=utf-8

###
### This script will only work, if there are only TWO accounts in the afa transaction
### at the end of a year: the one which will apply to the tax reduction afa list and
### the one from which it comes (inventory of the business). Example:
###
### 2016-12-31 * (a99) New NTG3 microphone
###   afa-tax-reduction:Microphones  € 100,00
###   inventory:NTG3 microphone
###



import sys, os, re, datetime, ledgerparse, ledger, tabulate



### SOME SETTINGS
#
# afa relevant account, month and day, decimal seperator
AFA_ACCOUNT	= 'ausgaben:job:absetzen:.*wirtschaftsgüter.*'
MONTH		= 12
DAY			= 31
DEC_SEP		= ','
#
### SOME SETTINGS





# functions

def gen_id(transaction, account_name):
	return transaction.code + '-' + transaction.payee + '-' + account_name



class LEDGER_CLASS(object):
	def __init__(self, journal):
		self.journal = journal

	def query_to_string(self, query):
		out = ledger.Balance()
		for post in self.journal.query(query):
			out += post.amount
		try:
			return str(out.to_amount().to_double()).replace('.', DEC_SEP)
		except Exception:
			return 0.0



class Afa_Transactions(object):
	def __init__(self, transaction, account_name, ledger, ledger_query, year=datetime.datetime.now().year):
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
		# get total costs (buy date amount)
		self.total_costs = ledgerparse.Money( ledq.query_to_string( '-l \"a>0\" -p "' + self.buy_date.strftime('%Y-%m-%d') + '" \"' + self.account + '\" and \"#' + self.transaction.code + '\"' ) )
		# get costs_begin = amount for that account last year
		self.costs_begin = ledgerparse.Money( ledq.query_to_string( '-p "to ' + str(year) + '-' + str(MONTH) + '-' + str(DAY) + '" \"' + self.account + '\" and \"#' + self.transaction.code + '\"' ) )
		# get costs_end = at end of the given year
		self.costs_end = ledgerparse.Money( ledq.query_to_string('-p "to ' + str(year+1) + '" \"' + self.account + '\" and \"#' + self.transaction.code + '\"') )

	def calculate_date(self, led):
		# iterate through all transactions of the ledger journal
		for l in led:
			# check if the transaction code is the same
			if l.code == self.transaction.code:
				for i, a in enumerate(l.accounts):
					# check if the account is in this transaction
					if self.account == a.name:
						# check if the date of the transaction is lower
						if l.aux_date < self.buy_date:
							# refresh temp date
							self.buy_date = l.aux_date

	def calculate_account(self, led, otherwise):
		# check which account of the transactions is < 0 and use this account name
		for y, acc in enumerate(self.transaction.accounts):
			if self.transaction.balance_account(y) < ledgerparse.Money('0'):
				return self.transaction.accounts[y].name

		# chaneg nothing otherwise
		return otherwise

	def costs_diff(self):
		return self.costs_begin - self.costs_end

	def __str__(self):
		return self.transaction.payee + ' (' + self.date_this_year.strftime('%Y-%m-%d') + '=' + self.buy_date.strftime('%Y-%m-%d') + ')'






# check parameter (need one: ledger-journal-file)
if len(sys.argv) < 2:
	print 'Need at least a ledger journal file as parameter.'
	exit()

# probably year given as parameter
if len(sys.argv) == 3:
	# get year into variable
	try:
		YEAR = int(sys.argv[2])
	except:
		# maybe it's the afa_account, use default year and parameter as afa_account
		YEAR = datetime.datetime.now().year
		AFA_ACCOUNT = sys.argv[2]

# three parameter given
if len(sys.argv) == 4:
	# get second as year
	try:
		YEAR = int(sys.argv[2])
	except:
		# somethign went wrong
		YEAR = datetime.datetime.now().year

	# get the 3rd as afa_account
	AFA_ACCOUNT = sys.argv[3]

# afa_account as 3rd parameter given



# get ledger journal into variable
LED		= ledgerparse.string_to_ledger( ledgerparse.ledger_file_to_string( sys.argv[1] ), True )
LEDGER	= LEDGER_CLASS( ledger.read_journal( sys.argv[1] ) )



# init transaction dict: TRANSACTION = array( Afa_Transaction(object) )
TRANSACTIONS = []

# get accounts which are afa-compliant the chosen year
for L in LED:
	# get only transactions done this year (aux date of afa transactions!!)
	if L.aux_date == datetime.datetime(YEAR, MONTH, DAY):
		# ... and those who HAVE a code
		if len(L.code) > 0:
			# ... and which names have afa account in it
			for i, acc in enumerate(L.accounts):
				if re.match(AFA_ACCOUNT, acc.name, re.IGNORECASE):
					# ... and only accounts which have amount > 0 on YEAR-12-31
					if L.balance_account(i).amount > 0:
						# and only if this does not already exists
						if gen_id(L, acc.name) not in [t.id for t in TRANSACTIONS]:
							TRANSACTIONS.append( Afa_Transactions(L, acc.name, LED, LEDGER, YEAR) )



# output the spicy stuff
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

def add_table_entry(date='', code='', item='', account='', costs='', costs_begin='', costs_diff='', costs_end=''):
	LINE_A = [unicode(date, 'utf-8'), YELLOW + unicode(code, 'utf-8') + E, BOLD + unicode(item, 'utf-8') + E, RED + unicode(costs, 'utf-8') + E, WHITE + unicode(costs_begin, 'utf-8') + E , CYAN + unicode(costs_diff, 'utf-8') + E, WHITE + unicode(costs_end, 'utf-8') + E]
	LINE_B = ['', '', PURPLE + unicode('   ' + account, 'utf-8') + E, '', '', '', '']
	return [ LINE_A, LINE_B ]


header = [ UNDERLINE + BOLD + BLUE + 'Kaufdatum', 'Beleg-Nr.', unicode('Gerät + Konto', 'utf-8'), 'Kaufpreis', 'Buchwert Anfang', 'Buchwert Diff', 'Buchwert Ende' + E ]
table = [header]


print
sum_costs = ledgerparse.Money('0')
sum_begin = ledgerparse.Money('0')
sum_diff = ledgerparse.Money('0')
sum_end = ledgerparse.Money('0')
for x in sorted(TRANSACTIONS, key=lambda y: y.buy_date):
	table.extend( add_table_entry( str(x.buy_date.strftime('%Y-%m-%d')), x.transaction.code, x.transaction.payee, str(x.account), str(x.total_costs), str(x.costs_begin), str(x.costs_diff()), str(x.costs_end) ) )
	sum_costs += x.total_costs
	sum_begin += x.costs_begin
	sum_diff += x.costs_diff()
	sum_end += x.costs_end

table.extend( add_table_entry() )
table.extend( add_table_entry(item='Summen:', costs=str(sum_costs), costs_begin=str(sum_begin), costs_diff=str(sum_diff), costs_end=str(sum_end)) )

print tabulate.tabulate(table, tablefmt='plain')
print