# -*- coding: utf-8 -*-


def post_init_hook(env):
    Seq = env["ir.sequence"].sudo()
    if not Seq.search([("code", "=", "salary.advance")], limit=1):
        Seq.create({
            "name": "Salary Advance",
            "code": "salary.advance",
            "prefix": "ANT-",
            "padding": 5,
            "company_id": False,
        })
