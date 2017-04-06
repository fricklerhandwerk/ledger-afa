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



import sys, os, datetime, ledgerparse, ledger



# afa relevant account
AFA_ACCOUNT	= 'wirtschaftsgüter'






# functions

def gen_id(transaction, account_name):
	return transaction.code + '-' + transaction.payee + '-' + account_name



class LEDGER_CLASS(object):
	def __init__(self, journal):
		self.journal = journal

	def query_to_double(self, query):
		out = ledger.Balance()
		for post in self.journal.query(query):
			out += post.amount
		return out.to_amount().to_double()



class Afa_Transactions(object):
	def __init__(self, transaction, account_name, ledger, year=datetime.datetime.now().year):
		self.transaction = transaction
		self.account = self.calculate_account(ledger, account_name)
		self.id = gen_id(transaction, account_name)

		self.buy_date = datetime.datetime.now()
		self.total_costs = ledgerparse.Money(real_amount=0)
		self.calculate_date_and_total_costs(ledger)

		self.costs_begin = ledgerparse.Money(real_amount=self.total_costs.amount)
		self.costs_end = ledgerparse.Money(real_amount=self.total_costs.amount)
		self.calculate_costs_begin_and_end(ledger, year)

	def calculate_costs_begin_and_end(self, led, year):
		# iterate through the years
		for Y in xrange(self.buy_date.year, year+1):
			# iterate through all transactions of the ledger journal
			for l in led:
				# check if the transaction code is the same
				if l.code == self.transaction.code:
					# check if the year is correct
					if l.date.year == Y:
						# check if there is an afa account in the transaction accounts
						if any(AFA_ACCOUNT.lower() in s.name.lower() for s in l.accounts):
							# check the correct account name
							for i, a in enumerate(l.accounts):
								if a.name == self.account:
									# THEN substract this amount from the total costs
									self.costs_end.amount -= abs( l.balance_account(i).amount )
									# also substract, if the year is not the chosen year
									if Y < year:
										self.costs_begin.amount -= abs( l.balance_account(i).amount )

	def calculate_date_and_total_costs(self, led):
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
							# and it's amount: first transaction should use total costs
							self.total_costs = l.balance_account(i)

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

# no year given - get actual year
if len(sys.argv) == 2:
	YEAR = datetime.datetime.now().year
else:
	# get year into variable
	try:
		YEAR = int(sys.argv[2])
	except:
		YEAR = datetime.datetime.now().year



# get ledger journal into variable
LED		= ledgerparse.string_to_ledger( ledgerparse.ledger_file_to_string( sys.argv[1] ), True )
LEDGER	= LEDGER_CLASS( ledger.read_journal( sys.argv[1] ) )



# init transaction dict: TRANSACTION = array( Afa_Transaction(object) )
TRANSACTIONS = []

# get accounts which are afa-compliant the chosen year
for L in LED:
	# get only transactions done this year on YEAR-12-31 (aux date of afa transactions!!)
	if L.aux_date == datetime.datetime(YEAR, 12, 31):
		# ... and those who HAVE a code
		if len(L.code) > 0:
			# ... and which names have afa account in it
			for i, acc in enumerate(L.accounts):
				if AFA_ACCOUNT.lower() in acc.name.lower():
					# ... and only accounts which have amount > 0 on YEAR-12-31
					if L.balance_account(i).amount > 0:
						# and only if this does not already exists
						if gen_id(L, acc.name) not in [t.id for t in TRANSACTIONS]:
							TRANSACTIONS.append( Afa_Transactions(L, acc.name, LED, YEAR) )


print LEDGER.query_to_double('ausgaben and not nicht')

exit()
for x in TRANSACTIONS:
	print x.transaction.payee + ' (' + x.transaction.code + ')' + ' .... ' + x.id
	print ' > ' + x.account
	print ' --- Kaufdatum: ' + str(x.buy_date.strftime('%Y-%m-%d'))
	print ' --- Anschaffungspreis: ' + str(x.total_costs)
	print ' --- Buchwert Beginn: ' + str(x.costs_begin)
	print ' --- Buchwert Differenz: ' + str(x.costs_diff())
	print ' --- Buchwert Ende: ' + str(x.costs_end)
	print