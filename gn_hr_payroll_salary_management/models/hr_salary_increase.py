# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class HrSalaryIncrease(models.Model):
    """Salary Increase - Individual or mass salary increases"""
    _name = "hr.salary.increase"
    _description = "Salary Increase"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(string="Nombre", required=True, tracking=True)
    date = fields.Date(
        string="Fecha efectiva",
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    increase_type = fields.Selection(
        [
            ("individual", "Individual"),
            ("department", "By Department"),
            ("all", "All Employees"),
        ],
        string="Increase Type",
        required=True,
        default="individual",
    )

    department_id = fields.Many2one(
        "hr.department",
        string="Department",
        help='Required if increase type is "By Department"',
    )

    employee_ids = fields.Many2many(
        "hr.employee",
        string="Employees",
        help='Required if increase type is "Individual"',
    )

    calculation_method = fields.Selection(
        [
            ("percentage", "Percentage"),
            ("fixed", "Fixed Amount"),
        ],
        string="Calculation Method",
        compute="_compute_calculation_method",
        store=True,
        readonly=False,
        help="Automatically determined based on which field has a value",
    )

    percentage = fields.Float(
        string="Percentage (%)",
        digits=(5, 2),
        help="Percentage increase (e.g., 10 for 10%)",
    )

    fixed_amount = fields.Float(
        string="Fixed Amount",
        digits=(12, 2),
        help="Fixed amount increase",
    )

    line_ids = fields.One2many("hr.employee.salary.line", "increase_id", string="Salary Lines")

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("validated", "Validated"),
        ],
        string="State",
        default="draft",
        required=True,
        tracking=True,
    )

    date_validated = fields.Datetime(string="Fecha de validación", readonly=True)

    notes = fields.Text(string="Notes")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                date_str = vals.get("date", fields.Date.today)
                if isinstance(date_str, str):
                    date_str = fields.Date.from_string(date_str)
                vals["name"] = _("Aumento Salarial - %s") % date_str
        return super().create(vals_list)

    @api.depends("percentage", "fixed_amount")
    def _compute_calculation_method(self):
        for rec in self:
            if rec.percentage:
                rec.calculation_method = "percentage"
            elif rec.fixed_amount:
                rec.calculation_method = "fixed"
            elif not rec.calculation_method:
                rec.calculation_method = "percentage"

    @api.constrains("increase_type", "department_id")
    def _check_required_fields(self):
        for rec in self:
            if rec.increase_type == "department" and not rec.department_id:
                raise ValidationError(_("Debe seleccionar un departamento para aumentos por departamento."))

    @api.constrains("percentage", "fixed_amount", "increase_type")
    def _check_calculation(self):
        for rec in self:
            if rec.increase_type == "individual":
                continue
            if not rec.percentage and not rec.fixed_amount:
                raise ValidationError(_("Debe especificar al menos un porcentaje o un monto fijo de aumento."))

    def action_get_employees(self):
        """Get employees based on increase type"""
        self.ensure_one()
        employees = self.env["hr.employee"]

        if self.increase_type == "all":
            employees = self.env["hr.employee"].search([
                ("active", "=", True),
                ("company_id", "=", self.company_id.id),
            ])
        elif self.increase_type == "department" and self.department_id:
            employees = self.env["hr.employee"].search([
                ("active", "=", True),
                ("department_id", "=", self.department_id.id),
                ("company_id", "=", self.company_id.id),
            ])
        elif self.increase_type == "individual":
            employees = self.employee_ids.filtered(lambda e: e.active)

        existing_employee_ids = self.line_ids.mapped("employee_id").ids
        for employee in employees:
            if employee.id not in existing_employee_ids:
                v = employee.current_version_id.sudo() if employee.current_version_id else False
                current_wage = v.wage or 0.0 if v else 0.0
                current_dept = v.department_id if v else False
                current_job = v.job_id if v else False
                if self.percentage:
                    new_wage = current_wage * (1 + self.percentage / 100.0)
                elif self.fixed_amount:
                    new_wage = current_wage + self.fixed_amount
                else:
                    new_wage = current_wage
                self.env["hr.employee.salary.line"].create({
                    "increase_id": self.id,
                    "employee_id": employee.id,
                    "current_wage": current_wage,
                    "new_wage": new_wage,
                    "current_department_id": current_dept.id if current_dept else False,
                    "new_department_id": current_dept.id if current_dept else False,
                    "current_job_id": current_job.id if current_job else False,
                    "new_job_id": current_job.id if current_job else False,
                })

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Empleados Obtenidos"),
                "message": _("Se obtuvieron %d empleados.") % len(employees),
                "type": "success",
            },
        }

    def action_validate(self):
        """Validate and apply salary increases"""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Debe obtener los empleados primero."))

        if self.state != "draft":
            raise UserError(_("Solo se pueden validar aumentos en estado borrador."))

        lines_with_changes = self.line_ids.filtered(lambda l: l.has_applied_change())
        if not lines_with_changes:
            if self.increase_type != "individual" and not self.percentage and not self.fixed_amount:
                raise UserError(_(
                    "Debe especificar al menos un porcentaje o monto fijo de aumento, o editar en las líneas: "
                    "nuevo salario, nuevo departamento o nuevo puesto."
                ))
            raise UserError(_(
                "Debe haber al menos una línea con cambio. Edite el nuevo salario, departamento o puesto en las líneas."
            ))

        for line in lines_with_changes:
            if not line.employee_id.current_version_id:
                raise UserError(_("El empleado %s no tiene una versión de contrato activa.") % line.employee_id.name)

            inc_pct = (
                ((line.new_wage / line.current_wage - 1) * 100) if line.current_wage > 0 else 0.0
            )
            self.env["hr.historical.salary.increase"].create({
                "employee_id": line.employee_id.id,
                "increase_id": self.id,
                "date": self.date,
                "previous_wage": line.current_wage,
                "new_wage": line.new_wage,
                "increase_amount": line.increase_amount,
                "increase_percentage": inc_pct,
                "previous_department_id": line.current_department_id.id if line.current_department_id else False,
                "new_department_id": line.new_department_id.id if line.new_department_id else False,
                "previous_job_id": line.current_job_id.id if line.current_job_id else False,
                "new_job_id": line.new_job_id.id if line.new_job_id else False,
            })

            version_vals = {
                "wage": line.new_wage,
                "department_id": line.new_department_id.id if line.new_department_id else False,
                "job_id": line.new_job_id.id if line.new_job_id else False,
            }
            line.employee_id.current_version_id.sudo().with_context(from_salary_increase=True).write(version_vals)

        self.write({
            "state": "validated",
            "date_validated": fields.Datetime.now(),
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Aumentos Validados"),
                "message": _("Se aplicaron %d aumentos salariales correctamente.") % len(lines_with_changes),
                "type": "success",
            },
        }

    def action_set_draft(self):
        """Revertir a borrador: restaurar en la versión vigente salario, departamento y puesto
        tal como estaban en la línea (snapshot previo a la validación). Solo líneas donde
        hubo cambio aplicado al validar (mismo criterio que has_applied_change)."""
        self.ensure_one()
        if self.state != "validated":
            raise UserError(_("Solo se pueden revertir aumentos validados."))

        lines_to_revert = self.line_ids.filtered(lambda l: l.has_applied_change())
        for line in lines_to_revert:
            if not line.employee_id.current_version_id:
                continue
            rw = {
                "wage": line.current_wage,
                "department_id": line.current_department_id.id if line.current_department_id else False,
                "job_id": line.current_job_id.id if line.current_job_id else False,
            }
            line.employee_id.current_version_id.sudo().with_context(from_salary_increase=True).write(rw)

        self.env["hr.historical.salary.increase"].search([("increase_id", "=", self.id)]).unlink()

        self.write({
            "state": "draft",
            "date_validated": False,
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Aumentos Revertidos"),
                "message": _(
                    "Se revirtió el aumento: salario, departamento y puesto quedaron como antes "
                    "de la validación (en la versión de contrato vigente)."
                ),
                "type": "info",
            },
        }


class HrEmployeeSalaryLine(models.Model):
    """Employee Salary Line - Individual salary increase, department or job change"""
    _name = "hr.employee.salary.line"
    _description = "Employee Salary Line"
    _order = "employee_id"

    increase_id = fields.Many2one(
        "hr.salary.increase",
        string="Salary Increase",
        required=True,
        ondelete="cascade",
    )
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)

    current_wage = fields.Float(string="Salario actual", digits=(12, 2), readonly=True)
    new_wage = fields.Float(string="Nuevo salario", digits=(12, 2), required=True)
    increase_amount = fields.Float(
        string="Monto aumento",
        digits=(12, 2),
        compute="_compute_increase_amount",
        store=True,
    )
    increase_percentage = fields.Float(
        string="% aumento",
        digits=(5, 2),
        compute="_compute_increase_percentage",
        store=True,
    )

    current_department_id = fields.Many2one("hr.department", string="Departamento actual", readonly=True)
    new_department_id = fields.Many2one("hr.department", string="Nuevo departamento")

    current_job_id = fields.Many2one("hr.job", string="Puesto actual", readonly=True)
    new_job_id = fields.Many2one("hr.job", string="Nuevo puesto")

    def has_applied_change(self):
        """True si la línea tenía al menos un cambio de salario, departamento o puesto respecto al snapshot.
        Debe coincidir con lo que aplica action_validate para revertir de forma consistente."""
        self.ensure_one()
        wage_change = self.increase_amount != 0
        dept_change = (self.new_department_id or self.current_department_id) and (
            self.new_department_id != self.current_department_id
        )
        job_change = (self.new_job_id or self.current_job_id) and self.new_job_id != self.current_job_id
        return wage_change or dept_change or job_change

    @api.depends("current_wage", "new_wage")
    def _compute_increase_amount(self):
        for rec in self:
            rec.increase_amount = rec.new_wage - rec.current_wage

    @api.depends("current_wage", "new_wage")
    def _compute_increase_percentage(self):
        for rec in self:
            if rec.current_wage > 0:
                rec.increase_percentage = ((rec.new_wage / rec.current_wage - 1) * 100)
            else:
                rec.increase_percentage = 0.0

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        if self.employee_id and self.employee_id.current_version_id:
            v = self.employee_id.current_version_id.sudo()
            self.current_wage = v.wage or 0.0
            self.current_department_id = v.department_id
            self.current_job_id = v.job_id
            self.new_department_id = v.department_id
            self.new_job_id = v.job_id
            if self.increase_id:
                if self.increase_id.percentage:
                    self.new_wage = self.current_wage * (1 + self.increase_id.percentage / 100.0)
                elif self.increase_id.fixed_amount:
                    self.new_wage = self.current_wage + self.increase_id.fixed_amount

    @api.model
    def _prepare_snapshot_values_from_employee(self, vals):
        """Completa salario/puesto/depto desde la versión vigente (create o write con employee_id)."""
        emp_id = vals.get("employee_id")
        if not emp_id:
            return vals
        out = dict(vals)
        emp = self.env["hr.employee"].browse(emp_id)
        v = emp.sudo().current_version_id
        if not v:
            return out
        cw = v.wage or 0.0
        d_id = v.department_id.id if v.department_id else False
        j_id = v.job_id.id if v.job_id else False
        if "current_wage" not in out:
            out["current_wage"] = cw
        elif out.get("current_wage") in (False, None):
            out["current_wage"] = cw
        if "current_department_id" not in out:
            out["current_department_id"] = d_id
        if "current_job_id" not in out:
            out["current_job_id"] = j_id
        if "new_department_id" not in out:
            out["new_department_id"] = d_id
        if "new_job_id" not in out:
            out["new_job_id"] = j_id
        if "new_wage" not in out or out.get("new_wage") in (False, None):
            inc_id = out.get("increase_id")
            base = out.get("current_wage", cw)
            if inc_id:
                inc = self.env["hr.salary.increase"].browse(inc_id)
                if inc.exists():
                    if inc.percentage:
                        out["new_wage"] = base * (1 + inc.percentage / 100.0)
                    elif inc.fixed_amount:
                        out["new_wage"] = base + inc.fixed_amount
                    else:
                        out["new_wage"] = base
                else:
                    out["new_wage"] = base
            else:
                out["new_wage"] = base
        return out

    @api.model_create_multi
    def create(self, vals_list):
        out_vals = []
        for vals in vals_list:
            vals = dict(vals)
            if vals.get("employee_id"):
                vals = self._prepare_snapshot_values_from_employee(vals)
            out_vals.append(vals)
        return super().create(out_vals)

    def write(self, vals):
        """Evita que un guardado parcial desde la lista editable borre el salario actual
        (snapshot) al cambiar solo puesto/departamento. Si cambia el empleado, rellenar snapshot."""
        vals = dict(vals)
        if vals.get("current_wage") in (False, None):
            vals.pop("current_wage", None)
        elif vals.get("current_wage") == 0 and any(rec.current_wage for rec in self):
            vals.pop("current_wage", None)
        if vals.get("employee_id"):
            self.ensure_one()
            merged = dict(vals)
            merged.setdefault("increase_id", self.increase_id.id)
            vals = self._prepare_snapshot_values_from_employee(merged)
        return super().write(vals)


class HrHistoricalSalaryIncrease(models.Model):
    """Historical Salary Increase - Track salary, department and job changes"""
    _name = "hr.historical.salary.increase"
    _description = "Historical Salary Increase"
    _order = "date desc, id desc"

    employee_id = fields.Many2one("hr.employee", string="Empleado", required=True, ondelete="cascade")
    increase_id = fields.Many2one("hr.salary.increase", string="Aumento", required=True, ondelete="cascade")
    date = fields.Date(string="Fecha", required=True)

    previous_wage = fields.Float(string="Salario anterior", digits=(12, 2))
    new_wage = fields.Float(string="Salario nuevo", digits=(12, 2))
    increase_amount = fields.Float(string="Monto aumento", digits=(12, 2))
    increase_percentage = fields.Float(string="% aumento", digits=(5, 2))

    previous_department_id = fields.Many2one("hr.department", string="Departamento anterior")
    new_department_id = fields.Many2one("hr.department", string="Departamento nuevo")
    previous_job_id = fields.Many2one("hr.job", string="Puesto anterior")
    new_job_id = fields.Many2one("hr.job", string="Puesto nuevo")

    notes = fields.Text(string="Notas", related="increase_id.notes", readonly=True)
