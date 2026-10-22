# -*- coding: utf-8 -*-


def _sync_payroll_compat_group_xmlids(env):
    """XML-IDs tipo Enterprise (group_hr_payroll_*) → mismos res.groups que officer/manager CE."""
    IMD = env["ir.model.data"].sudo()
    mapping = (
        ("group_hr_payroll_user", "group_hn_payroll_user"),
        ("group_hr_payroll_manager", "group_hn_payroll_manager"),
    )
    for alias, target_xml in mapping:
        target = env.ref(f"l10n_hn_payroll_base.{target_xml}", raise_if_not_found=False)
        if not target:
            continue
        row = IMD.search(
            [
                ("module", "=", "l10n_hn_payroll_base"),
                ("name", "=", alias),
            ],
            limit=1,
        )
        if row:
            old_gid = row.res_id if row.model == "res.groups" else None
            vals = {"model": "res.groups", "res_id": target.id, "noupdate": True}
            if row.model != "res.groups" or row.res_id != target.id or not row.noupdate:
                row.write(vals)
            if old_gid and old_gid != target.id:
                old_g = env["res.groups"].browse(old_gid)
                if old_g.exists():
                    target.users |= old_g.users
        else:
            IMD.create(
                {
                    "name": alias,
                    "module": "l10n_hn_payroll_base",
                    "model": "res.groups",
                    "res_id": target.id,
                    "noupdate": True,
                }
            )


def _backfill_payroll_structure_types(env):
    """Enterprise-style: every structure should have a type (default: Employee)."""
    employee_type = env.ref("hr.structure_type_employee", raise_if_not_found=False)
    if not employee_type:
        return
    structures = env["hr.payroll.structure"].sudo().search([("type_id", "=", False)])
    if structures:
        structures.write({"type_id": employee_type.id})


def post_init_hook(env):
    _sync_payroll_compat_group_xmlids(env)
    _backfill_payroll_structure_types(env)
