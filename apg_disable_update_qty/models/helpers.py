# -*- coding: utf-8 -*-

def ensure_inventory_privilege(env):
    """Return whether the current user belongs to the authorized group."""
    return env.user.has_group("apg_disable_update_qty.group_onhand_qty_user")
