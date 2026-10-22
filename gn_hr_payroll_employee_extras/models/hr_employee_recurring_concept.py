# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_compare
from markupsafe import escape
from datetime import date, datetime
from dateutil.relativedelta import relativedelta


class HrEmployeeRecurringConcept(models.Model):
    """Conceptos recurrentes de ingresos y deducciones por empleado."""
    _name = 'hr.employee.recurring.concept'
    _description = 'Concepto recurrente del empleado'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'company_id, employee_id, date_start desc'
    
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=False,
        ondelete='cascade',
        check_company=True,
        tracking=True,
        domain="[('company_id', '=', company_id)]",
        help='Dejar vacío para crear un concepto compartido que puede asignarse a múltiples empleados',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        help='Compañía de la plantilla o del empleado. Con empleado asignado debe coincidir con la compañía del empleado.',
    )

    # Flag to identify shared concepts
    is_shared = fields.Boolean(string='Es Compartido', compute='_compute_is_shared', store=True,
                              help='Indica si este concepto es compartido (sin empleado específico)')

    is_template = fields.Boolean(
        string='Plantilla',
        default=False,
        help='Marcar cuando este registro define una plantilla de catálogo (sin empleado ni origen copiado).',
    )

    @api.depends('employee_id')
    def _compute_is_shared(self):
        """Compute if concept is shared (no employee assigned)"""
        for rec in self:
            rec.is_shared = not bool(rec.employee_id)
    
    # Field to select from existing recurring concepts (shows as "Concept Name" in the form)
    name_from_concept_id = fields.Many2one(
        "hr.employee.recurring.concept",
        string="Plantilla del Concepto",
        domain="['&', '&', ('is_template', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id), ('id', '!=', id)]",
        help="Seleccione una plantilla de catálogo (is_template); "
        "también puede escribir un nombre nuevo abajo sin elegir plantilla.",
    )
    
    name = fields.Char(string='Nombre del Concepto', required=True, tracking=True,
                      help='Nombre del concepto. Se llena automáticamente al seleccionar un concepto recurrente existente arriba')
    
    # Code for salary rules (required for shared concepts, optional for employee-specific)
    code = fields.Char(string='Código', tracking=True,
                      help='Código único para identificar este concepto en las reglas salariales. Requerido para conceptos compartidos. Se puede copiar desde otro concepto recurrente o especificar manualmente.')
    
    concept_type = fields.Selection([
        ('income', 'Ingreso'),
        ('deduction', 'Deducción'),
    ], string='Tipo', required=True, default='deduction', tracking=True,
       help='Ingreso o deducción. Por defecto deducción; al elegir plantilla se toma el tipo de la plantilla.')
    
    amount_type = fields.Selection([
        ('fixed', 'Monto fijo'),
        ('percentage', 'Porcentaje del salario base'),
    ], string='Tipo de monto', required=True, default='fixed', tracking=True)
    
    amount = fields.Float(string='Monto', digits=(12, 2), required=True, tracking=True,
                         help='Monto fijo o porcentaje. Con «Ambas quincenas» sin dividir: se descuenta '
                         'íntegro en cada quincena. Con dividir activo: total mensual a repartir entre '
                         '1.ª y 2.ª quincena (pestaña Quincenas).')
    
    # Loan fields
    is_loan = fields.Boolean(string='Es préstamo', default=False, tracking=True)
    total_amount = fields.Float(
        string='Monto total del préstamo',
        digits=(12, 2),
        compute='_compute_total_amount',
        store=True,
        readonly=True,
        tracking=True,
        help='Suma de las cuotas fijas (monto × número de cuotas, o primera cuota diferenciada). '
        'No incluye el monto residual.',
    )
    loan_residual_amount = fields.Float(
        string='Monto residual',
        digits=(12, 2),
        default=0.0,
        tracking=True,
        help='Cuota adicional opcional tras las cuotas fijas. Si es mayor que cero, '
        'se genera un descuento extra por ese monto.',
    )
    loan_total_manual = fields.Boolean(
        string='Total manual (obsoleto)',
        default=False,
        help='Campo legado; ya no se usa. El total se calcula desde monto y cuotas.',
    )
    loan_last_installment_amount = fields.Float(
        string='Cuota adicional (residuo)',
        digits=(12, 2),
        compute='_compute_loan_last_installment_amount',
        help='Igual al monto residual cuando aplica una cuota extra.',
    )
    loan_has_residual = fields.Boolean(
        string='Tiene residuo en última cuota',
        compute='_compute_loan_has_residual',
        store=True,
        help='True cuando la última cuota difiere del monto habitual por un total manual o residuo.',
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Moneda',
    )
    loan_installments_remaining = fields.Integer(
        string='Cuotas restantes',
        compute='_compute_loan_dashboard_fields',
        store=True,
    )
    loan_total_payment_count = fields.Integer(
        string='Total de descuentos',
        compute='_compute_loan_dashboard_fields',
        store=True,
        help='Cuotas fijas más una adicional si el total del préstamo deja residuo.',
    )
    loan_progress_percent = fields.Float(
        string='Progreso del préstamo (%)',
        compute='_compute_loan_dashboard_fields',
        store=True,
    )
    loan_stage = fields.Selection(
        [
            ('active', 'Activo'),
            ('almost_done', 'Por finalizar'),
            ('residual', 'Con residuo'),
            ('done', 'Liquidado'),
        ],
        string='Estado del préstamo',
        compute='_compute_loan_dashboard_fields',
        store=True,
    )
    gn_next_deduction_amount = fields.Float(
        string='Próximo descuento',
        digits=(12, 2),
        compute='_compute_gn_next_deduction_fields',
    )
    gn_next_apply_biweek_label = fields.Char(
        string='Próxima quincena',
        compute='_compute_gn_next_deduction_fields',
    )
    payslip_input_ids = fields.One2many(
        'hr.payslip.input',
        'recurring_concept_id',
        string='Aplicaciones en nómina',
    )
    payslip_input_count = fields.Integer(
        string='Recibos vinculados',
        compute='_compute_payslip_input_count',
    )
    gn_form_has_warning = fields.Boolean(
        string='Tiene advertencias en formulario',
        compute='_compute_gn_form_warning_html',
    )
    gn_form_warning_html = fields.Html(
        string='Advertencias del formulario',
        compute='_compute_gn_form_warning_html',
        sanitize=False,
    )
    installments = fields.Integer(
        string='Número de cuotas',
        default=1,
        compute='_compute_installments',
        store=True,
        readonly=False,
        tracking=True,
        help='Número de cuotas. Se calcula automáticamente desde fecha inicio, fecha fin y aplicar en quincena cuando están definidos.'
    )
    paid_installments = fields.Integer(
        string='Cuotas pagadas',
        default=0,
        compute='_compute_paid_installments',
        store=True,
        readonly=False,
        inverse='_inverse_paid_installments',
        tracking=True,
        help='Cuotas pagadas = Cuotas iniciales pagadas + cuotas pagadas en nómina.'
    )
    initial_paid_installments = fields.Integer(
        string='Cuotas iniciales pagadas',
        default=0,
        help='Cuotas pagadas antes de que el empleado fuera incluido en la nómina (ej: préstamo iniciado en otro sistema).'
    )
    manual_paid_installments = fields.Integer(
        string='Cuotas pagadas en nómina',
        default=0,
        help='Cuotas pagadas mediante nómina al validar el recibo.'
    )
    remaining_amount = fields.Float(string='Saldo pendiente', digits=(12, 2),
                                    compute='_compute_remaining_amount', store=True)
    
    # Dates (date_start obligatorio salvo plantilla de préstamo: is_template + is_loan)
    date_start = fields.Date(string='Fecha inicio', default=fields.Date.today, tracking=True)
    date_end = fields.Date(string='Fecha fin', tracking=True)
    
    for_payroll = fields.Boolean(string='Para Planilla', default=False,
                                 help='Incluir en selector de conceptos de Beneficios/Deducciones en Planilla')

    # Biweekly application (only relevant for biweekly structures)
    apply_biweek = fields.Selection([
        ('both', 'Ambas Quincenas'),
        ('first', 'Primera Quincena (1-15)'),
        ('second', 'Segunda Quincena (16-fin)'),
    ], string='Aplicar en Quincena', default='both',
       help='Quincenal: «Ambas» aplica en las dos nóminas del mes. Sin dividir monto, cada quincena '
       'descuenta el monto íntegro; con «Dividir monto entre quincenas» el monto es el total mensual '
       'repartido entre 1.ª y 2.ª quincena. Mensual: se ignora.')

    loan_split_quota_across_biweeks = fields.Boolean(
        string='Dividir monto entre 1.ª y 2.ª quincena',
        default=False,
        help='Con «Ambas quincenas» y nómina quincenal: indique el monto a descontar en la '
        '1.ª quincena; en la 2.ª se deduce el resto del monto del periodo (p. ej. 150 + 100 = 250 al mes). '
        'Si deja «Monto 1.ª quincena» en 0, se reparte mitad y mitad. '
        'Si no está marcado, cada quincena aplica el monto íntegro del concepto.',
    )
    loan_first_biweek_amount = fields.Float(
        string='Monto 1.ª quincena',
        digits=(12, 2),
        default=0.0,
        help='Monto a descontar en la primera quincena (días 1–15). La segunda quincena deduce '
        'automáticamente el resto (monto del periodo menos este valor). En 0: reparto equitativo. '
        'Para monto fijo, no puede superar el «Monto» del concepto (total del periodo mensual).',
    )
    first_quota_differentiated = fields.Boolean(
        string='Primera cuota diferenciada',
        default=False,
        help='Solo préstamos: si está activo y «Monto primera cuota» > 0, la primera cuota pendiente '
        '(cuotas pagadas = 0) usa ese monto en lugar del monto habitual; el particionado entre quincenas '
        'sigue aplicando sobre ese valor.',
    )
    first_quota_amount = fields.Float(
        string='Monto primera cuota',
        digits=(12, 2),
        default=0.0,
        help='Monto a descontar en la primera cuota del préstamo. Las siguientes cuotas usan el campo Monto.',
    )
    loan_second_biweek_reference = fields.Float(
        string='2.ª quincena (referencia)',
        digits=(12, 2),
        compute='_compute_loan_second_biweek_reference',
        help='Solo referencia para monto fijo: Amount − monto 1.ª (o mitad si 1.ª es 0). En porcentaje no aplica.',
    )

    @api.depends(
        'is_loan',
        'loan_split_quota_across_biweeks',
        'amount_type',
        'amount',
        'loan_first_biweek_amount',
        'first_quota_differentiated',
        'first_quota_amount',
        'paid_installments',
        'installments',
        'total_amount',
        'loan_total_manual',
    )
    def _compute_loan_second_biweek_reference(self):
        for rec in self:
            if not rec.loan_split_quota_across_biweeks or rec.amount_type != 'fixed':
                rec.loan_second_biweek_reference = 0.0
                continue
            if rec.is_loan:
                idx = rec.paid_installments
                if idx >= (rec.installments or 0):
                    rec.loan_second_biweek_reference = 0.0
                    continue
                amt = rec._gn_loan_installment_amount(idx)
            else:
                amt = rec.amount or 0.0
            first = rec.loan_first_biweek_amount or 0.0
            if first <= 0:
                rec.loan_second_biweek_reference = round(amt / 2.0, 2)
            else:
                rec.loan_second_biweek_reference = round(amt - first, 2)

    # Nombres antiguos aún referenciados por vistas personalizadas / copias en BD (pre 19.0.1.0.27).
    # string distinto de los campos destino para evitar avisos "Two fields (...) have the same label".
    loan_quota_biweek_weight_first = fields.Float(
        string='Compat.: monto 1.ª quincena',
        related='loan_first_biweek_amount',
        readonly=False,
    )
    loan_quota_biweek_weight_second = fields.Float(
        string='Compat.: referencia 2.ª quincena',
        related='loan_second_biweek_reference',
        readonly=True,
    )

    active = fields.Boolean(string='Activo', default=True, tracking=True)
    
    # Applicability criteria (for shared concepts - replaces master concept functionality)
    applies_to_all = fields.Boolean(string='Aplica a Todos los Empleados', default=False,
                                    help='Si está marcado, este concepto puede asignarse a todos los empleados')
    department_ids = fields.Many2many(
        'hr.department',
        string='Departamentos',
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        help='Si no aplica a todos, especificar departamentos específicos',
    )
    job_ids = fields.Many2many(
        'hr.job',
        string='Puestos de Trabajo',
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        help='Si no aplica a todos, especificar puestos específicos',
    )
    structure_type_ids = fields.Many2many('hr.payroll.structure.type', string='Tipos de Estructura',
                                         help='Tipos de estructura de nómina donde aplica este concepto')
    
    description = fields.Text(string='Descripción',
                             help='Descripción detallada del concepto')
    
    
    # Keep template_concept_id for backward compatibility but it's now redundant
    # name_from_concept_id serves the same purpose
    # Note: This field is hidden in views, not in the model definition
    template_concept_id = fields.Many2one('hr.employee.recurring.concept', 
                                         string='Copiar de Concepto Recurrente',
                                         domain="[('employee_id', '=', employee_id), ('id', '!=', id)]",
                                         help='Campo oculto para compatibilidad. Use name_from_concept_id en su lugar.')
    
    notes = fields.Text(string='Notas')
    
    @api.model
    def default_get(self, fields_list):
        """Set default employee_id from context"""
        res = super().default_get(fields_list)
        # Get employee_id from context if available (when creating from employee form)
        # If not in context, leave empty to allow creating shared concepts
        if self.env.context.get('default_is_template'):
            res['is_template'] = True
            res['employee_id'] = False
            res['name_from_concept_id'] = False
            res['date_start'] = False
            res['company_id'] = self.env.context.get('default_company_id') or self.env.company.id
        elif 'default_employee_id' in self.env.context:
            eid = self.env.context['default_employee_id']
            res['employee_id'] = eid
            emp = self.env['hr.employee'].browse(eid)
            if emp.company_id:
                res['company_id'] = emp.company_id.id
        elif 'default_company_id' in self.env.context:
            res['company_id'] = self.env.context['default_company_id']
        res.setdefault('company_id', self.env.company.id)
        res.setdefault('concept_type', 'deduction')
        tid = self.env.context.get('default_name_from_concept_id')
        if tid:
            tpl = self.env['hr.employee.recurring.concept'].browse(tid)
            if tpl.exists():
                if not fields_list or 'name' in fields_list:
                    res.setdefault('name', tpl.name)
                if not fields_list or 'code' in fields_list:
                    res.setdefault('code', tpl.code)
                if not fields_list or 'amount' in fields_list:
                    res.setdefault('amount', tpl.amount)
                if not fields_list or 'amount_type' in fields_list:
                    res.setdefault('amount_type', tpl.amount_type)
                if not fields_list or 'concept_type' in fields_list:
                    res.setdefault('concept_type', tpl.concept_type)
        return res

    @api.model
    def _fill_code_from_template_vals(self, vals, record=None):
        """Completa nombre y código desde la plantilla si faltan en vals.

        El onchange del formulario ya copia en memoria; esto cubre guardados vía RPC, listas
        editables del empleado (campos readonly no se envían) e importación.

        :param record: opcional, registro(s) en write cuando `vals` no incluye la plantilla;
          si es un solo registro y `name_from_concept_id` no viene en vals, se usa la del registro.
        """
        vals = dict(vals)
        tid = vals.get('name_from_concept_id')
        if tid is None and record is not None and len(record) == 1:
            tid = record.name_from_concept_id.id
        if not tid or vals.get('is_template'):
            return vals
        src = self.env['hr.employee.recurring.concept'].browse(tid)
        if not src.exists():
            return vals
        if not (vals.get('name') or '').strip() and src.name:
            vals['name'] = src.name
        if not (vals.get('code') or '').strip() and src.code:
            vals['code'] = src.code
        if not vals.get('concept_type') and src.concept_type:
            vals['concept_type'] = src.concept_type
        if not vals.get('amount_type') and src.amount_type:
            vals['amount_type'] = src.amount_type
        self._gn_merge_template_amount_into_vals(vals, record, src)
        return vals

    @api.model
    def _gn_merge_template_amount_into_vals(self, vals, record, src):
        """Completa amount desde plantilla sin pisar un monto ya guardado o enviado."""
        amount_in_vals = vals.get('amount')
        has_nonzero_in_vals = (
            amount_in_vals is not None
            and float_compare(amount_in_vals or 0.0, 0.0, precision_digits=2) != 0
        )
        record_amount = 0.0
        if record is not None and len(record) == 1:
            record_amount = record.amount or 0.0
        if has_nonzero_in_vals:
            return vals
        if float_compare(record_amount, 0.0, precision_digits=2) != 0:
            if 'amount' in vals and float_compare(amount_in_vals or 0.0, 0.0, precision_digits=2) == 0:
                del vals['amount']
            return vals
        if 'amount' not in vals or float_compare(amount_in_vals or 0.0, 0.0, precision_digits=2) == 0:
            if not vals.get('is_loan') or src.amount:
                vals['amount'] = src.amount
        return vals

    @api.model
    def _amount_is_provided(self, vals):
        return 'amount' in vals and vals['amount'] is not None and vals['amount'] is not False

    @api.model
    def _gn_should_drop_spurious_zero_amount(self, vals, record):
        """Ignorar amount=0 cuando el registro ya tenía monto y la UI no lo envió."""
        if 'amount' not in vals:
            return False
        if float_compare(vals['amount'], 0.0, precision_digits=2) != 0:
            return False
        if record is None or len(record) != 1:
            return False
        if float_compare(record.amount or 0.0, 0.0, precision_digits=2) == 0:
            return False
        if set(vals.keys()) == {'amount'}:
            return False
        return True

    @api.model
    def _fill_missing_amount_vals(self, vals, record=None):
        """Cuota en préstamos: readonly en lista embebida; no inferir desde total."""
        vals = dict(vals)
        if self._gn_should_drop_spurious_zero_amount(vals, record):
            del vals['amount']
        if self._amount_is_provided(vals):
            return vals
        if record is not None and len(record) == 1 and record.amount:
            return vals
        return vals

    def _gn_effective_amount_before_onchange(self):
        """Monto previo al onchange: formulario en memoria o registro guardado."""
        current = self.amount or 0.0
        if float_compare(current, 0.0, precision_digits=2) != 0:
            return current
        if self._origin and float_compare(self._origin.amount or 0.0, 0.0, precision_digits=2) != 0:
            return self._origin.amount
        return 0.0

    def _gn_protect_amount_after_onchange(self, template_amount=None):
        """Conserva el monto ya ingresado; la plantilla solo rellena si estaba vacío."""
        prev = self._gn_effective_amount_before_onchange()
        if float_compare(prev, 0.0, precision_digits=2) != 0:
            self.amount = prev
            return
        if (
            template_amount is not None
            and float_compare(template_amount or 0.0, 0.0, precision_digits=2) != 0
        ):
            self.amount = template_amount

    @api.model
    def _template_loan_cleared_values(self):
        return {
            'installments': 0,
            'initial_paid_installments': 0,
            'manual_paid_installments': 0,
            'loan_split_quota_across_biweeks': False,
            'loan_first_biweek_amount': 0.0,
            'first_quota_differentiated': False,
            'first_quota_amount': 0.0,
            'loan_residual_amount': 0.0,
            'date_start': False,
            'date_end': False,
        }

    @api.model_create_multi
    def create(self, vals_list):
        cleaned = []
        for vals in vals_list:
            vals = dict(vals)
            emp_id = vals.get('employee_id')
            if emp_id:
                emp = self.env['hr.employee'].browse(emp_id)
                if emp.company_id:
                    vals['company_id'] = emp.company_id.id
            if vals.get('is_template'):
                vals['name_from_concept_id'] = False
            if vals.get('is_template') and vals.get('is_loan'):
                vals.update(self._template_loan_cleared_values())
            if not vals.get('concept_type') and vals.get('name_from_concept_id'):
                src = self.env['hr.employee.recurring.concept'].browse(
                    vals['name_from_concept_id']
                )
                if src and src.concept_type:
                    vals['concept_type'] = src.concept_type
            if not vals.get('concept_type'):
                vals['concept_type'] = 'deduction'
            vals = self._fill_code_from_template_vals(vals)
            vals = self._fill_missing_amount_vals(vals)
            cleaned.append(vals)
        records = super().create(cleaned)
        return records

    def write(self, vals):
        if self.env.context.get('skip_hr_recurring_template_loan_clear'):
            return super().write(vals)
        vals = dict(vals)
        vals = self._fill_code_from_template_vals(vals, self)
        vals = self._fill_missing_amount_vals(vals, self)
        if vals.get('employee_id'):
            emp = self.env['hr.employee'].browse(vals['employee_id'])
            if emp.company_id:
                vals['company_id'] = emp.company_id.id
        if vals.get('is_template'):
            vals['name_from_concept_id'] = False
        res = super().write(vals)
        self._sync_code_from_template_if_empty()
        to_clear = self.filtered(lambda r: r.is_template and r.is_loan)
        if to_clear:
            to_clear.with_context(skip_hr_recurring_template_loan_clear=True).write(
                self._template_loan_cleared_values()
            )
        return res

    def _sync_code_from_template_if_empty(self):
        """Repara registros con plantilla pero sin nombre o código (datos previos al arreglo)."""
        if self.env.context.get('skip_recurring_code_from_template_resync'):
            return
        for rec in self:
            if not rec.name_from_concept_id or rec.is_template:
                continue
            tpl = rec.name_from_concept_id
            updates = {}
            if tpl.name and not (rec.name or '').strip():
                updates['name'] = tpl.name
            tcode = (tpl.code or '').strip()
            if tcode and not (rec.code or '').strip():
                updates['code'] = tpl.code
            if not rec.amount and tpl.amount:
                updates['amount'] = tpl.amount
            elif rec.is_loan and not rec.amount and rec.total_amount and rec.installments:
                stub = self._fill_missing_amount_vals({
                    'is_loan': True,
                }, rec)
                if stub.get('amount'):
                    updates['amount'] = stub['amount']
            if updates:
                rec.with_context(skip_recurring_code_from_template_resync=True).write(updates)

    @api.constrains('employee_id', 'company_id')
    def _check_employee_company_matches(self):
        for rec in self:
            if rec.employee_id and rec.employee_id.company_id and rec.company_id != rec.employee_id.company_id:
                raise ValidationError(
                    _('La compañía del concepto debe coincidir con la compañía del empleado.')
                )

    @api.constrains('date_start', 'is_template')
    def _check_date_start_required_unless_template(self):
        for rec in self:
            if rec.is_template:
                continue
            if not rec.date_start:
                raise ValidationError(_('La fecha de inicio es obligatoria.'))

    @api.constrains('is_template', 'employee_id', 'name_from_concept_id')
    def _check_template_flags(self):
        for rec in self:
            if rec.is_template:
                if rec.employee_id:
                    raise ValidationError(
                        _('Una plantilla no puede tener empleado asignado.')
                    )
                if rec.name_from_concept_id:
                    raise ValidationError(
                        _('Una plantilla de catálogo no puede referenciar otra plantilla como origen.')
                    )

    @api.constrains('employee_id', 'name', 'code', 'applies_to_all', 'department_ids', 'job_ids')
    def _check_shared_concept(self):
        """Validate shared concepts"""
        for rec in self:
            if not rec.employee_id:  # Es concepto compartido
                # Shared concept must have a name and code
                if not rec.name:
                    raise ValidationError(_('Los conceptos compartidos deben tener un nombre.'))
                if not rec.code:
                    raise ValidationError(_('Los conceptos compartidos deben tener un código para las reglas salariales.'))
                
                # Validate applicability criteria
                if not rec.applies_to_all and not rec.department_ids and not rec.job_ids:
                    # Allow empty criteria - user can assign manually via wizard
                    pass
    
    def action_assign_to_employees(self):
        """Assign this shared recurring concept to multiple employees"""
        self.ensure_one()
        if self.employee_id:
            raise UserError(_('Este concepto ya está asignado a un empleado específico. Solo los conceptos compartidos pueden asignarse a múltiples empleados.'))
        
        if not self.active:
            raise UserError(_('El concepto debe estar activo para asignarlo a empleados.'))
        
        # Check if concept has applicability criteria for automatic assignment
        has_criteria = self.applies_to_all or self.department_ids or self.job_ids
        
        if has_criteria:
            # Automatic assignment based on criteria (like master concepts)
            return self._assign_by_criteria()
        else:
            # Manual selection via wizard
            return {
                'type': 'ir.actions.act_window',
                'name': _('Asignar Concepto a Empleados'),
                'res_model': 'hr.employee.recurring.concept.assign.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_concept_id': self.id,
                }
            }
    
    def _assign_by_criteria(self):
        """Assign concept to employees based on applicability criteria"""
        self.ensure_one()
        
        # Build domain for eligible employees
        domain = [
            ('active', '=', True),
            ('company_id', '=', self.company_id.id),
        ]
        
        if not self.applies_to_all:
            if self.department_ids:
                domain.append(('department_id', 'in', self.department_ids.ids))
            if self.job_ids:
                domain.append(('job_id', 'in', self.job_ids.ids))
        
        employees = self.env['hr.employee'].search(domain)
        
        created_count = 0
        for employee in employees:
            # Check if employee already has this concept (by code)
            existing = self.env['hr.employee.recurring.concept'].search([
                ('employee_id', '=', employee.id),
                ('code', '=', self.code),
                ('active', '=', True),
            ])
            
            if not existing:
                # Check if employee's structure type matches
                v_sudo = employee.current_version_id.sudo() if employee.current_version_id else False
                if v_sudo and v_sudo.structure_type_id:
                    if self.structure_type_ids and v_sudo.structure_type_id.id not in self.structure_type_ids.ids:
                        continue
                
                # Create recurring concept for employee
                # For loans, don't copy total_amount from shared concept - each employee can have different amount
                inst = (
                    (self.installments if self.installments and self.installments > 0 else 1)
                    if self.is_loan
                    else 1
                )
                vals = {
                    'employee_id': employee.id,
                    'company_id': self.company_id.id,
                    'name': self.name,
                    'code': self.code,
                    'concept_type': self.concept_type,
                    'amount_type': self.amount_type,
                    'amount': self.amount,
                    'is_loan': self.is_loan,
                    'installments': inst,
                    'loan_residual_amount': self.loan_residual_amount if self.is_loan else 0.0,
                    'date_start': self.date_start or fields.Date.context_today(self),
                    'date_end': self.date_end,
                    'apply_biweek': self.apply_biweek,
                    'loan_split_quota_across_biweeks': self.loan_split_quota_across_biweeks,
                    'loan_first_biweek_amount': self.loan_first_biweek_amount,
                    'first_quota_differentiated': (
                        self.first_quota_differentiated if self.is_loan else False
                    ),
                    'first_quota_amount': (
                        self.first_quota_amount if self.is_loan else 0.0
                    ),
                    'active': True,
                    'is_template': False,
                }
                self.env['hr.employee.recurring.concept'].create(vals)
                created_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Conceptos Asignados'),
                'message': _('Se asignaron %d conceptos a empleados elegibles basados en los criterios de aplicabilidad.') % created_count,
                'type': 'success',
            }
        }
    
    @api.onchange('name_from_concept_id')
    def _onchange_name_from_concept_id(self):
        """Auto-fill all fields when selecting an existing recurring concept"""
        template_amount = None
        if self.name_from_concept_id:
            template = self.name_from_concept_id
            template_amount = template.amount
            self.name = template.name
            self.code = template.code  # Copy code from template
            self.concept_type = template.concept_type
            self.amount_type = template.amount_type
            self.is_loan = template.is_loan
            if template.is_loan:
                if template.is_template and template.is_loan and not template.installments:
                    self.installments = 1
                else:
                    self.installments = template.installments
                self.loan_residual_amount = template.loan_residual_amount
            
            # Copy applicability criteria if copying from shared concept to shared concept
            if not self.employee_id and not template.employee_id:
                self.applies_to_all = template.applies_to_all
                self.department_ids = template.department_ids
                self.job_ids = template.job_ids
                self.structure_type_ids = template.structure_type_ids
                self.description = template.description
            
            # Copy biweekly application setting
            self.apply_biweek = template.apply_biweek
            self.loan_split_quota_across_biweeks = template.loan_split_quota_across_biweeks
            self.loan_first_biweek_amount = template.loan_first_biweek_amount
            self.first_quota_differentiated = (
                template.first_quota_differentiated if template.is_loan else False
            )
            self.first_quota_amount = (
                template.first_quota_amount if template.is_loan else 0.0
            )
            
            # Don't copy dates, notes, or paid_installments as those are specific to each concept
        self._gn_protect_amount_after_onchange(template_amount=template_amount)
    
    @api.constrains(
        'loan_split_quota_across_biweeks',
        'loan_first_biweek_amount',
        'amount',
        'amount_type',
        'apply_biweek',
    )
    def _check_loan_split_quota_biweeks(self):
        for rec in self:
            if not rec.loan_split_quota_across_biweeks:
                continue
            if rec.apply_biweek != 'both':
                raise ValidationError(
                    _('Para repartir el monto entre quincenas debe elegir «Ambas quincenas» en «Aplicar en Quincena».')
                )
            if rec.loan_first_biweek_amount < 0:
                raise ValidationError(_('El monto de la 1.ª quincena no puede ser negativo.'))
            if rec.amount_type == 'fixed' and rec.loan_first_biweek_amount > 0:
                cap = rec._gn_loan_split_cap_amount()
                if float_compare(
                    rec.loan_first_biweek_amount,
                    cap,
                    precision_digits=2,
                ) > 0:
                    raise ValidationError(
                        _('El monto de la 1.ª quincena no puede ser mayor que el monto del periodo '
                          '(monto habitual o monto primera cuota si aplica).')
                    )

    @api.onchange('is_loan')
    def _onchange_is_loan_clear_split(self):
        if not self.is_loan:
            self.first_quota_differentiated = False
            self.first_quota_amount = 0.0
        self._gn_protect_amount_after_onchange()

    @api.onchange('apply_biweek')
    def _onchange_apply_biweek_clear_loan_split(self):
        if self.apply_biweek != 'both':
            self.loan_split_quota_across_biweeks = False
        self._gn_protect_amount_after_onchange()

    @api.onchange('loan_split_quota_across_biweeks', 'loan_first_biweek_amount')
    def _onchange_biweek_split_preserve_amount(self):
        self._gn_protect_amount_after_onchange()

    @api.onchange('is_template')
    def _onchange_is_template(self):
        if self.is_template:
            if self.employee_id:
                self.is_template = False
                self._gn_protect_amount_after_onchange()
                return {
                    'warning': {
                        'title': _('No aplicable'),
                        'message': _(
                            'No puede marcar como plantilla un concepto vinculado a un empleado.'
                        ),
                    }
                }
            self.name_from_concept_id = False
        self._gn_protect_amount_after_onchange()

    @api.onchange('is_template', 'is_loan')
    def _onchange_template_loan_clear_fields(self):
        if self.is_template and self.is_loan:
            self.installments = 0
            self.initial_paid_installments = 0
            self.manual_paid_installments = 0
            self.loan_split_quota_across_biweeks = False
            self.loan_first_biweek_amount = 0.0
            self.first_quota_differentiated = False
            self.first_quota_amount = 0.0
            self.date_start = False
            self.date_end = False
        self._gn_protect_amount_after_onchange()

    @api.onchange('company_id')
    def _onchange_company_id(self):
        """Limitar empleado/departamento/puesto a la compañía del concepto (ignora visibilidad cross-company)."""
        if self.company_id:
            if self.employee_id and self.employee_id.company_id != self.company_id:
                self.employee_id = False
            if self.department_ids:
                self.department_ids = self.department_ids.filtered(
                    lambda d: d.company_id == self.company_id
                )
            if self.job_ids:
                self.job_ids = self.job_ids.filtered(
                    lambda j: j.company_id == self.company_id
                )
        self._gn_protect_amount_after_onchange()

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        """Ajustar compañía al cambiar empleado; conservar plantillas de catálogo."""
        if self.employee_id:
            self.is_template = False
            if self.employee_id.company_id:
                self.company_id = self.employee_id.company_id
            if self.name_from_concept_id:
                src = self.name_from_concept_id
                if src.is_template:
                    if src.company_id and src.company_id != self.company_id:
                        self.name_from_concept_id = False
                elif src.employee_id and src.employee_id != self.employee_id:
                    self.name_from_concept_id = False
            if (
                self.template_concept_id
                and self.template_concept_id.employee_id
                and self.template_concept_id.employee_id != self.employee_id
            ):
                self.template_concept_id = False
        self._gn_protect_amount_after_onchange()
    
    def _calculate_loan_end_date(self, start, installments, apply_biweek):
        """Calcular fecha fin del préstamo dado fecha inicio, cuotas y quincena.

        Itera quincenas hacia adelante desde *start* y devuelve la fecha de
        cierre de la última quincena cuando se alcanza el número de cuotas.
        """
        if not start or not installments or installments <= 0:
            return False
        apply = apply_biweek or 'both'
        count = 0
        current = date(start.year, start.month, 1)
        last_period_end = None
        max_months = installments * 2 + 12

        for _ in range(max_months):
            first_biweek_end = date(current.year, current.month, 15)
            month_end = current + relativedelta(months=1) - relativedelta(days=1)

            if apply in ('both', 'first') and first_biweek_end >= start:
                count += 1
                last_period_end = first_biweek_end
                if count >= installments:
                    break

            if apply in ('both', 'second') and month_end >= start:
                count += 1
                last_period_end = month_end
                if count >= installments:
                    break

            current += relativedelta(months=1)

        return last_period_end

    @api.model
    def count_application_periods(self, date_start, date_end, apply_biweek):
        """Número de períodos de aplicación quincenal entre dos fechas (solape con primera y/o segunda quincena).

        Misma lógica que ``_compute_installments`` para conceptos no préstamo.
        Sin ``date_end`` o sin solape válido devuelve 1 (p. ej. concepto indefinido).
        """
        if not date_start or not date_end or not apply_biweek or date_end < date_start:
            return 1
        count = 0
        start = date_start
        end = date_end
        current = date(start.year, start.month, 1)
        end_month_first = date(end.year, end.month, 1)

        while current <= end_month_first:
            first_biweek_start = current
            first_biweek_end = date(current.year, current.month, 15)
            second_biweek_start = date(current.year, current.month, 16)
            second_biweek_end = current + relativedelta(months=1) - relativedelta(days=1)

            def overlaps(period_start, period_end):
                return not (period_end < start or period_start > end)

            if apply_biweek in ("both", "first"):
                if overlaps(first_biweek_start, first_biweek_end):
                    count += 1
            if apply_biweek in ("both", "second"):
                if overlaps(second_biweek_start, second_biweek_end):
                    count += 1

            current += relativedelta(months=1)

        return max(1, count)

    @api.onchange('is_loan', 'installments', 'apply_biweek', 'date_start', 'initial_paid_installments')
    def _onchange_loan_compute_end_date(self):
        """Para préstamos: calcular date_end desde cuotas restantes, apply_biweek y date_start."""
        if self.is_loan and self.date_start and self.installments and self.installments > 0:
            remaining = self.installments - (self.paid_installments or 0)
            if remaining > 0:
                end = self._calculate_loan_end_date(self.date_start, remaining, self.apply_biweek)
                if end:
                    self.date_end = end
        self._gn_protect_amount_after_onchange()

    @api.depends('date_start', 'date_end', 'apply_biweek', 'is_loan')
    def _compute_installments(self):
        """Calcular cuotas desde fecha inicio, fecha fin y aplicar en quincena.

        Para préstamos (is_loan=True) el usuario ingresa las cuotas directamente
        y date_end se calcula desde ellas (vía onchange); no se sobreescribe aquí.

        Para conceptos regulares (no préstamo) con nómina quincenal Honduras:
        - both: 2 cuotas por mes (primera y segunda quincena)
        - first: 1 cuota por mes (solo días 1-15)
        - second: 1 cuota por mes (solo días 16-fin)
        """
        for rec in self:
            if rec.is_loan:
                continue

            if not rec.date_start or not rec.date_end or not rec.apply_biweek:
                rec.installments = 1
                continue
            if rec.date_end < rec.date_start:
                rec.installments = 1
                continue

            count = 0
            start = rec.date_start
            end = rec.date_end

            current = date(start.year, start.month, 1)
            end_month_first = date(end.year, end.month, 1)

            while current <= end_month_first:
                first_biweek_start = current
                first_biweek_end = date(current.year, current.month, 15)
                second_biweek_start = date(current.year, current.month, 16)
                second_biweek_end = current + relativedelta(months=1) - relativedelta(days=1)

                def overlaps(period_start, period_end):
                    return not (period_end < start or period_start > end)

                if rec.apply_biweek in ('both', 'first'):
                    if overlaps(first_biweek_start, first_biweek_end):
                        count += 1
                if rec.apply_biweek in ('both', 'second'):
                    if overlaps(second_biweek_start, second_biweek_end):
                        count += 1

                current += relativedelta(months=1)

            rec.installments = max(1, count)

    @staticmethod
    def _gn_version_pay_periodicity_key(version):
        """Periodicidad para prorratear % sobre salario.

        Si existe el campo ``periodicity`` (p. ej. localización HN), se usa;
        si no, se infiere desde ``schedule_pay`` (hr_payroll).
        """
        if not version:
            return "monthly"
        per = (getattr(version, "periodicity", None) or "").lower()
        sched = (getattr(version, "schedule_pay", None) or "").lower()
        if not per and sched in ("bi-weekly", "biweekly"):
            per = "biweekly"
        if per in ("biweekly", "bi-weekly") or sched in ("bi-weekly", "biweekly"):
            return "biweekly"
        if per == "weekly" or sched == "weekly":
            return "weekly"
        return "monthly"

    def _gn_loan_default_total_amount(self):
        """Total sugerido del préstamo (monto fijo × cuotas, con primera cuota diferenciada si aplica)."""
        self.ensure_one()
        if not self.is_loan or not self.installments:
            return 0.0
        if self.amount_type != 'fixed':
            return self.total_amount or 0.0
        if (
            self.first_quota_differentiated
            and (self.first_quota_amount or 0.0) > 0
        ):
            return round(
                (self.first_quota_amount or 0.0)
                + max(0, self.installments - 1) * (self.amount or 0.0),
                2,
            )
        return round((self.amount or 0.0) * self.installments, 2)

    def _gn_loan_fixed_payments_sum(self):
        """Suma de las cuotas fijas (sin la cuota adicional por residuo)."""
        self.ensure_one()
        n = self.installments or 0
        if n <= 0:
            return 0.0
        if (
            self.first_quota_differentiated
            and (self.first_quota_amount or 0.0) > 0
        ):
            return round(
                (self.first_quota_amount or 0.0) + max(0, n - 1) * (self.amount or 0.0),
                2,
            )
        return round(n * (self.amount or 0.0), 2)

    def _gn_loan_residual_amount(self):
        """Monto de la cuota adicional (campo editable)."""
        self.ensure_one()
        if not self.is_loan or self.amount_type != 'fixed':
            return 0.0
        return round(max(0.0, self.loan_residual_amount or 0.0), 2)

    def _gn_loan_grand_total(self):
        """Deuda total = cuotas fijas + monto residual."""
        self.ensure_one()
        return round((self.total_amount or 0.0) + self._gn_loan_residual_amount(), 2)

    def _gn_loan_total_payment_count(self):
        """Número total de descuentos: cuotas fijas + 1 si hay residuo positivo."""
        self.ensure_one()
        n = self.installments or 0
        if n <= 0:
            return 0
        if self._gn_loan_residual_amount() > 0:
            return n + 1
        return n

    def _gn_loan_last_installment_amount(self):
        """Monto de la cuota adicional por residuo (0 si no aplica)."""
        self.ensure_one()
        residual = self._gn_loan_residual_amount()
        return residual if residual > 0 else 0.0

    def _gn_loan_installment_amount(self, installment_index):
        """Monto del descuento en installment_index (0 = primera pendiente)."""
        self.ensure_one()
        n = self.installments or 0
        if n <= 0:
            return self.amount or 0.0
        idx = int(installment_index)
        if idx < 0:
            return 0.0
        if idx >= n:
            if idx == n and self._gn_loan_residual_amount() > 0:
                return self._gn_loan_residual_amount()
            return 0.0
        if (
            self.first_quota_differentiated
            and (self.first_quota_amount or 0.0) > 0
            and idx == 0
        ):
            return self.first_quota_amount
        return self.amount or 0.0

    def _gn_loan_deducted_through_installment(self, paid_count):
        """Suma descontada tras paid_count descuentos pagados."""
        self.ensure_one()
        if paid_count <= 0:
            return 0.0
        total_payments = self._gn_loan_total_payment_count()
        total_deducted = 0.0
        for i in range(min(paid_count, total_payments)):
            total_deducted += self._gn_loan_installment_amount(i)
        return round(total_deducted, 2)

    def _gn_loan_is_complete(self):
        self.ensure_one()
        return self.paid_installments >= self._gn_loan_total_payment_count()

    @api.depends(
        'loan_residual_amount',
        'amount',
        'installments',
        'is_loan',
        'amount_type',
        'first_quota_differentiated',
        'first_quota_amount',
    )
    def _compute_loan_last_installment_amount(self):
        for rec in self:
            if not rec.is_loan or rec.amount_type != 'fixed' or not rec.installments:
                rec.loan_last_installment_amount = 0.0
                continue
            rec.loan_last_installment_amount = rec._gn_loan_last_installment_amount()

    @api.depends(
        'loan_residual_amount',
        'amount',
        'installments',
        'is_loan',
        'amount_type',
        'first_quota_differentiated',
        'first_quota_amount',
    )
    def _compute_loan_has_residual(self):
        for rec in self:
            if not rec.is_loan or rec.amount_type != 'fixed' or not rec.installments:
                rec.loan_has_residual = False
                continue
            last_amt = rec._gn_loan_residual_amount()
            rec.loan_has_residual = float_compare(last_amt, 0.0, 2) > 0

    _APPLY_BIWEEK_LABELS = {
        'both': 'Ambas quincenas',
        'first': '1.ª quincena',
        'second': '2.ª quincena',
    }

    @api.depends(
        'is_loan',
        'installments',
        'paid_installments',
        'loan_has_residual',
        'active',
        'remaining_amount',
        'total_amount',
        'loan_residual_amount',
        'amount',
        'first_quota_differentiated',
        'first_quota_amount',
        'amount_type',
    )
    def _compute_loan_dashboard_fields(self):
        for rec in self:
            if not rec.is_loan or not rec.installments:
                rec.loan_installments_remaining = 0
                rec.loan_total_payment_count = 0
                rec.loan_progress_percent = 0.0
                rec.loan_stage = False
                continue
            total_payments = rec._gn_loan_total_payment_count()
            rec.loan_total_payment_count = total_payments
            remaining_inst = max(0, total_payments - rec.paid_installments)
            rec.loan_installments_remaining = remaining_inst
            rec.loan_progress_percent = min(
                100.0,
                round(100.0 * rec.paid_installments / total_payments, 2),
            ) if total_payments else 0.0
            if rec.paid_installments >= total_payments:
                rec.loan_stage = 'done'
            elif not rec.active and (rec.remaining_amount or 0.0) <= 0:
                rec.loan_stage = 'done'
            elif remaining_inst <= 1 and rec.paid_installments < total_payments:
                rec.loan_stage = 'almost_done'
            elif rec.loan_has_residual:
                rec.loan_stage = 'residual'
            else:
                rec.loan_stage = 'active'

    @api.depends('payslip_input_ids')
    def _compute_payslip_input_count(self):
        for rec in self:
            rec.payslip_input_count = len(rec.payslip_input_ids)

    def _gn_estimate_period_base_amount(self):
        """Monto base del periodo para monto fijo o porcentaje (sin split quincenal)."""
        self.ensure_one()
        if self.amount_type == 'fixed':
            return self.amount or 0.0
        if not self.employee_id:
            return 0.0
        version = (
            self.employee_id.current_version_id.sudo()
            if self.employee_id.current_version_id
            else False
        )
        wage = (version.wage if version else 0.0) or self.employee_id.wage or 0.0
        if not wage:
            return 0.0
        per_key = self._gn_version_pay_periodicity_key(version) if version else 'monthly'
        if per_key == 'biweekly':
            period_wage = wage / 2.0
        elif per_key == 'weekly':
            period_wage = wage / 4.33
        else:
            period_wage = wage
        return round((period_wage * (self.amount or 0.0)) / 100.0, 2)

    @api.depends(
        'is_loan',
        'paid_installments',
        'installments',
        'amount',
        'amount_type',
        'apply_biweek',
        'employee_id',
        'employee_id.current_version_id',
        'employee_id.current_version_id.wage',
        'first_quota_differentiated',
        'first_quota_amount',
        'total_amount',
        'loan_residual_amount',
    )
    def _compute_gn_next_deduction_fields(self):
        for rec in self:
            rec.gn_next_apply_biweek_label = rec._APPLY_BIWEEK_LABELS.get(
                rec.apply_biweek or 'both', ''
            )
            if not rec.active:
                rec.gn_next_deduction_amount = 0.0
                continue
            if rec.is_loan:
                if rec._gn_loan_is_complete():
                    rec.gn_next_deduction_amount = 0.0
                    continue
                base = rec._gn_effective_recurring_deduction_base(
                    rec._gn_estimate_period_base_amount()
                )
            else:
                base = rec._gn_estimate_period_base_amount()
            rec.gn_next_deduction_amount = base or 0.0

    def _gn_collect_ux_warning_lines(self):
        """Mensajes informativos de configuración (sin popup; se muestran en el formulario)."""
        self.ensure_one()
        lines = []
        has_error = False
        if self.is_loan and self.amount_type == 'fixed' and self.installments:
            residual = self._gn_loan_residual_amount()
            if residual > 0:
                lines.append(
                    _(
                        'Tras %(n)d cuotas de %(amount)s, se descontará una cuota '
                        'adicional de %(residual)s.'
                    )
                    % {
                        'n': self.installments,
                        'amount': self.amount or 0.0,
                        'residual': residual,
                    }
                )
        if self.date_start and self.date_end and self.date_end < self.date_start:
            has_error = True
            lines.append(_('La fecha fin no puede ser anterior a la fecha inicio.'))
        if (
            self.loan_split_quota_across_biweeks
            and (self.loan_first_biweek_amount or 0.0) > 0
        ):
            cap = self._gn_loan_split_cap_amount()
            if (self.loan_first_biweek_amount or 0.0) > cap:
                lines.append(
                    _('El monto de la 1.ª quincena supera la cuota del periodo (%(cap)s).')
                    % {'cap': cap}
                )
        if self.amount_type == 'percentage' and self.employee_id:
            if not self._gn_estimate_period_base_amount():
                lines.append(
                    _(
                        'No hay salario en el contrato vigente; el porcentaje no generará '
                        'monto hasta tener sueldo.'
                    )
                )
        return lines, has_error

    @api.depends(
        'total_amount',
        'amount',
        'installments',
        'is_loan',
        'loan_first_biweek_amount',
        'loan_split_quota_across_biweeks',
        'date_start',
        'date_end',
        'first_quota_amount',
        'first_quota_differentiated',
        'amount_type',
        'employee_id',
        'employee_id.current_version_id',
        'employee_id.current_version_id.wage',
    )
    def _compute_gn_form_warning_html(self):
        for rec in self:
            lines, has_error = rec._gn_collect_ux_warning_lines()
            rec.gn_form_has_warning = bool(lines)
            if not lines:
                rec.gn_form_warning_html = False
                continue
            alert_class = 'alert-danger' if has_error else 'alert-warning'
            items = ''.join(f'<li>{escape(line)}</li>' for line in lines)
            rec.gn_form_warning_html = (
                f'<div class="alert {alert_class} mb-0" role="alert">'
                f'<i class="fa fa-exclamation-triangle me-2"></i>'
                f'<ul class="mb-0 ps-3">{items}</ul></div>'
            )

    def action_view_payslip_inputs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Aplicaciones en nómina'),
            'res_model': 'hr.payslip.input',
            'view_mode': 'list,form',
            'domain': [('recurring_concept_id', '=', self.id)],
            'context': {'default_recurring_concept_id': self.id},
        }

    def _gn_notification(self, title, message, ntype='success'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': ntype,
                'sticky': False,
            },
        }

    @api.depends(
        'amount',
        'installments',
        'amount_type',
        'is_loan',
        'first_quota_differentiated',
        'first_quota_amount',
        'employee_id.current_version_id',
        'employee_id.current_version_id.wage',
        'employee_id.current_version_id.schedule_pay',
    )
    def _compute_total_amount(self):
        """Monto total = suma de cuotas fijas (monto × cuotas)."""
        for rec in self:
            if not rec.is_loan or not rec.installments:
                rec.total_amount = 0.0
                continue
            if rec.amount_type == 'fixed':
                rec.total_amount = rec._gn_loan_fixed_payments_sum()
            elif rec.amount_type == 'percentage' and rec.employee_id:
                version = rec.employee_id.current_version_id.sudo() if rec.employee_id.current_version_id else False
                if version and version.wage:
                    wage = version.wage
                    per_key = rec._gn_version_pay_periodicity_key(version)
                    if per_key == "biweekly":
                        amount_per_period = (wage / 2.0) * (rec.amount / 100.0)
                    elif per_key == "weekly":
                        amount_per_period = (wage / 4.33) * (rec.amount / 100.0)
                    else:
                        amount_per_period = wage * (rec.amount / 100.0)
                    if (
                        rec.first_quota_differentiated
                        and (rec.first_quota_amount or 0.0) > 0
                    ):
                        rec.total_amount = round(
                            (rec.first_quota_amount or 0.0)
                            + max(0, rec.installments - 1) * amount_per_period,
                            2,
                        )
                    else:
                        rec.total_amount = round(amount_per_period * rec.installments, 2)
                else:
                    rec.total_amount = 0.0
            else:
                rec.total_amount = 0.0

    @api.depends('initial_paid_installments', 'manual_paid_installments')
    def _compute_paid_installments(self):
        """Cuotas pagadas = cuotas iniciales (antes de nómina) + cuotas pagadas en nómina."""
        for rec in self:
            rec.paid_installments = rec.initial_paid_installments + rec.manual_paid_installments

    def _inverse_paid_installments(self):
        """Al escribir paid_installments, ajustar manual_paid_installments."""
        for rec in self:
            rec.manual_paid_installments = max(0, rec.paid_installments - rec.initial_paid_installments)

    @api.constrains('first_quota_amount', 'first_quota_differentiated', 'is_loan', 'concept_type')
    def _check_first_quota_amount_positive(self):
        for rec in self:
            if not rec.first_quota_differentiated:
                continue
            if not rec.is_loan:
                raise ValidationError(
                    _('«Primera cuota diferenciada» solo aplica a conceptos marcados como préstamo.')
                )
            if rec.concept_type != 'deduction':
                raise ValidationError(
                    _('«Primera cuota diferenciada» solo aplica a deducciones.')
                )
            if rec.first_quota_amount < 0:
                raise ValidationError(_('El monto de la primera cuota no puede ser negativo.'))

    @api.depends(
        'total_amount',
        'loan_residual_amount',
        'amount',
        'paid_installments',
        'installments',
        'first_quota_differentiated',
        'first_quota_amount',
        'is_loan',
    )
    def _compute_remaining_amount(self):
        for rec in self:
            if rec.is_loan and rec._gn_loan_grand_total() > 0:
                paid = rec.paid_installments
                if paid <= 0:
                    rec.remaining_amount = rec._gn_loan_grand_total()
                elif rec.amount_type == 'fixed':
                    deducted = rec._gn_loan_deducted_through_installment(paid)
                    rec.remaining_amount = round(rec._gn_loan_grand_total() - deducted, 2)
                elif (
                    rec.first_quota_differentiated
                    and (rec.first_quota_amount or 0.0) > 0
                ):
                    deducted = rec.first_quota_amount + rec.amount * max(0, paid - 1)
                    rec.remaining_amount = rec._gn_loan_grand_total() - deducted
                else:
                    deducted = rec.amount * paid
                    rec.remaining_amount = rec._gn_loan_grand_total() - deducted
            else:
                rec.remaining_amount = 0.0

    @api.constrains('amount_type', 'amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount_type == 'percentage' and (rec.amount < 0 or rec.amount > 100):
                raise ValidationError(_('El porcentaje debe estar entre 0 y 100.'))
    
    @api.constrains('is_loan', 'total_amount', 'installments', 'employee_id')
    def _check_loan(self):
        for rec in self:
            if rec.is_loan:
                if rec.is_template and rec.is_loan:
                    continue
                # total_amount opcional en conceptos compartidos (plantilla): crear regla y asignar a múltiples empleados
                # con montos distintos. En conceptos por empleado también puede dejarse vacío al asignar; se completa después.
                if not rec.installments or rec.installments <= 0:
                    raise ValidationError(_('Debe especificar el número de cuotas.'))

    @api.constrains('loan_residual_amount', 'is_loan')
    def _check_loan_residual_amount(self):
        for rec in self:
            if rec.is_loan and (rec.loan_residual_amount or 0.0) < 0:
                raise ValidationError(_('El monto residual no puede ser negativo.'))
    
    @api.model
    def _gn_employee_version_is_biweekly(self, employee):
        """True si el contrato vigente del empleado es nómina quincenal."""
        if not employee:
            return False
        version = employee.current_version_id.sudo() if employee.current_version_id else False
        if not version:
            return False
        periodicity = getattr(version, "periodicity", None)
        if periodicity == "biweekly":
            return True
        sched = getattr(version, "schedule_pay", None) or ""
        return sched in ("biweekly", "bi-weekly")

    def _gn_loan_split_cap_amount(self):
        """Tope para validar monto 1.ª quincena = monto del periodo."""
        self.ensure_one()
        if not self.is_loan:
            if self.amount_type == 'fixed':
                return self.amount or 0.0
            return self._gn_estimate_period_base_amount()
        idx = self.paid_installments
        if idx >= (self.installments or 0):
            return self.amount or 0.0
        return self._gn_loan_installment_amount(idx)

    def _gn_effective_recurring_deduction_base(self, computed_base_amount):
        """Monto base de la cuota antes de partir por quincenas (préstamo, residuo y primera cuota)."""
        self.ensure_one()
        if self.concept_type != 'deduction' or not self.is_loan:
            return float(computed_base_amount or 0.0)
        idx = self.paid_installments
        if idx >= self._gn_loan_total_payment_count():
            return 0.0
        if self.amount_type == 'fixed':
            return float(self._gn_loan_installment_amount(idx))
        if (
            self.first_quota_differentiated
            and (self.first_quota_amount or 0.0) > 0
            and idx == 0
        ):
            return float(self.first_quota_amount)
        return float(computed_base_amount or 0.0)

    def _gn_apply_loan_biweek_split_to_amount(self, base_amount, employee, period_ref_date=None):
        """Dividir monto + ambas quincenas + contrato quincenal: 1.ª monto fijo; 2.ª = resto.

        :param base_amount: monto completo del periodo para este recibo (fijo o % ya aplicado).
        :param period_ref_date: ``date_from`` del recibo o fecha del anticipo.
        """
        self.ensure_one()
        if not base_amount:
            return base_amount
        if not (
            self.loan_split_quota_across_biweeks
            and self.apply_biweek == "both"
            and self._gn_employee_version_is_biweekly(employee)
        ):
            return base_amount
        if not period_ref_date:
            return base_amount
        ref = fields.Date.to_date(period_ref_date)
        is_first_biweek = ref.day <= 15
        first_cfg = self.loan_first_biweek_amount or 0.0
        base = base_amount
        if first_cfg <= 0:
            half = round(base / 2.0, 2)
            return half
        first_eff = round(min(first_cfg, base), 2)
        second_eff = round(base - first_eff, 2)
        return first_eff if is_first_biweek else second_eff

    def action_mark_paid(self):
        """Marcar cuota como pagada (incrementa manual_paid_installments)."""
        self.ensure_one()
        if not self.is_loan:
            raise UserError(_('Solo se pueden marcar cuotas para conceptos de préstamo.'))
        if self.paid_installments >= self._gn_loan_total_payment_count():
            raise UserError(_('Todas las cuotas ya han sido pagadas.'))
        next_before = self.gn_next_deduction_amount
        total_payments = self._gn_loan_total_payment_count()
        self.manual_paid_installments += 1
        finished = self.paid_installments >= total_payments
        if finished:
            self.active = False
        body = _(
            'Cuota %(paid)d/%(total)d registrada manualmente.',
            paid=self.paid_installments,
            total=total_payments,
        )
        if finished:
            body = _('Préstamo liquidado (%(paid)d/%(total)d cuotas). Concepto desactivado.') % {
                'paid': self.paid_installments,
                'total': total_payments,
            }
        self.message_post(body=body)
        if finished:
            msg = _('Préstamo liquidado. Se desactivó el concepto «%(name)s».') % {
                'name': self.name,
            }
        else:
            msg = _(
                'Cuota %(paid)d de %(total)d registrada. Próximo descuento estimado: %(amount).2f',
                paid=self.paid_installments,
                total=total_payments,
                amount=self.gn_next_deduction_amount or next_before,
            )
        return self._gn_notification(_('Cuota registrada'), msg)
