# -*- coding: utf-8 -*-


def post_init_hook(env):
    Marital = env["l10n_hn_hr_recruitment.marital.status"]
    for emp in env["hr.employee"].search(
        [("marital", "!=", False), ("marital_status_id", "=", False)]
    ):
        ms = Marital.search([("code", "=", emp.marital)], limit=1)
        if ms:
            emp.marital_status_id = ms.id
    for app in env["hr.applicant"].search(
        [("marital", "!=", False), ("marital_status_id", "=", False)]
    ):
        code = app.marital if app.marital != "others" else "other"
        ms = Marital.search([("code", "=", code)], limit=1)
        if ms:
            app.marital_status_id = ms.id
    FieldStudy = env["l10n_hn_hr_recruitment.field.of.study"]
    for emp in env["hr.employee"].search(
        [("study_field", "!=", False), ("study_field_id", "=", False)]
    ):
        text = (emp.study_field or "").strip()
        if not text:
            continue
        fs = FieldStudy.search([("name", "=ilike", text)], limit=1)
        if fs:
            emp.study_field_id = fs.id
