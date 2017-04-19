import ledger_afa


def test_get_sub_accounts(journal):
    top = journal.find_account_re('AfA')
    assert top is not None
    accounts = ledger_afa.get_sub_accounts(top)
    assert len(accounts) > 0


def test_get_afa_posts(journal):
    posts = ledger_afa.get_afa_posts(journal, 'AfA', 2017)
    assert len(posts) > 0


def test_get_inventory(journal):
    posts = ledger_afa.get_afa_posts(journal, 'AfA', 2017)
    inventory = ledger_afa.get_inventory(posts)
    assert len(inventory) > 0
