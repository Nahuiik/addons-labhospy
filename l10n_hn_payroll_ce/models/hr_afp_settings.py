# © 2025 Grupo Nahuiik

from odoo import api, fields, models


class HrAfpSettings(models.Model):
    _name = "hr.afp.settings"
    _description = "AFP Settings"
    _order = "create_date desc"

    name = fields.Char(string="Nombre", required=True, default="AFP")
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
        required=True,
    )
    pay_periodicity = fields.Selection(
        [
            ("weekly", "Semanal"),
            ("bi-weekly", "Quincenal"),
            ("monthly", "Mensual"),
        ],
        string="Periodicidad Pago",
        default="monthly",
        required=True,
    )
    include_in = fields.Selection(
        [
            ("first", "Primera Quincena"),
            ("second", "Segunda Quincena"),
            ("both", "Ambas Quincenas"),
        ],
        string="Incluir En",
        default="first",
        required=True,
    )
    apply_percentage = fields.Float(
        string="Porcentaje Aplicar (%)", digits=(12, 4), required=True, default=0.0
    )
    minimum_ceiling = fields.Float(string="Techo AFP Mínimo", digits=(12, 2), default=0.0)
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("validated", "Validado"),
        ],
        string="Estado",
        default="draft",
        required=True,
    )
    line_ids = fields.One2many(
        "hr.afp.settings.line",
        "afp_id",
        string="Empleados",
    )
    total_afp_amount = fields.Float(
        string="Total AFP",
        compute="_compute_totals",
        store=True,
        digits=(12, 2),
    )
    total_quincena_amount = fields.Float(
        string="Total Quincenal",
        compute="_compute_totals",
        store=True,
        digits=(12, 2),
    )

    def set_afp(self):
        for rec in self:
            rec.state = "validated"

    def set_to_draft(self):
        self.write({"state": "draft"})

    def action_get_employees(self):
        for rec in self:
            employees = rec._get_target_employees()
            commands = [(5, 0, 0)]
            for employee in employees:
                wage = rec._get_employee_wage(employee)
                difference = max(wage - (rec.minimum_ceiling or 0.0), 0.0)
                afp_amount = difference * (rec.apply_percentage or 0.0) / 100.0
                period_divisor = rec._get_period_divisor()
                quincena_amount = afp_amount / period_divisor if period_divisor else afp_amount
                commands.append(
                    (0, 0, {
                        "employee_id": employee.id,
                        "current_wage": wage,
                        "difference": difference,
                        "quincena_amount": quincena_amount,
                        "afp_amount": afp_amount,
                    })
                )
            rec.line_ids = commands

    def _get_period_divisor(self):
        self.ensure_one()
        if self.pay_periodicity == "monthly":
            return 2
        if self.pay_periodicity == "bi-weekly":
            return 1 if self.include_in in ("first", "second") else 2
        if self.pay_periodicity == "weekly":
            return 4 if self.include_in == "both" else 1
        return 1

    def _get_target_employees(self):
        self.ensure_one()
        return self.env["hr.employee"].search([
            ("company_id", "=", self.company_id.id),
            ("active", "=", True),
        ])

    def _get_employee_wage(self, employee):
        self.ensure_one()
        wage_fields = [
            "contract_wage",
            "wage",
        ]
        for field_name in wage_fields:
            value = getattr(employee, field_name, 0.0)
            if value:
                return value
        version = employee.version_id
        if version and version.wage:
            return version.wage
        return 0.0

    @api.depends("line_ids.afp_amount", "line_ids.quincena_amount")
    def _compute_totals(self):
        for rec in self:
            rec.total_afp_amount = sum(rec.line_ids.mapped("afp_amount"))
            rec.total_quincena_amount = sum(rec.line_ids.mapped("quincena_amount"))


class HrAfpSettingsLine(models.Model):
    _name = "hr.afp.settings.line"
    _description = "AFP Settings Line"
    _order = "employee_id"

    afp_id = fields.Many2one(
        "hr.afp.settings",
        string="Configuración AFP",
        required=True,
        ondelete="cascade",
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Empleado",
        required=True,
    )
    company_id = fields.Many2one(
        related="afp_id.company_id",
        store=True,
        readonly=True,
    )
    current_wage = fields.Float(string="Salario Actual", digits=(12, 2))
    difference = fields.Float(string="Diferencia", digits=(12, 2))
    quincena_amount = fields.Float(string="Quincenal", digits=(12, 2))
    afp_amount = fields.Float(string="Monto AFP", digits=(12, 2))
