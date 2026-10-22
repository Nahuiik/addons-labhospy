
from . import models
from . import wizard
from . import controllers


def _init_parent_path(env):
    """Initialize parent_path for existing accounts after module installation."""
    AccountAccount = env["account.account"]
    if getattr(AccountAccount, "_parent_store", False):
        accounts = AccountAccount.search([])
        if accounts:
            accounts._parent_store_compute()
