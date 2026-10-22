from odoo import api, fields, models, _
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    gts_no_exigir_sucursal = fields.Boolean(
        string='Sucursal Opcional',
        default=False,
        help='Si está activo, el campo Sucursal deja de ser obligatorio en este documento.',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        is_entry = (
            res.get('move_type') == 'entry'
            or self.env.context.get('default_move_type') == 'entry'
        )
        if is_entry and 'gts_no_exigir_sucursal' in fields_list:
            res['gts_no_exigir_sucursal'] = False
        return res

    @api.model
    def _get_default_branch(self):
        User = self.env['res.users']
        return User.browse(self.env.uid).branch_id.id or False

    @api.model
    def _get_default_template(self):
        user_branch = self.env['res.users'].browse(self.env.uid).branch_id.id
        template = self.env['report.template.settings'].search([('branch_id', '=', user_branch)])
        return template.id or False

    branch_id = fields.Many2one('res.branch', 'Branch', default=_get_default_branch)
    comment = fields.Char(string="Comment")

    @api.onchange('branch_id')
    def onchange_branch_id(self):
        if self.branch_id:
            if self.branch_id.term_conditions1:
                self.comment = self.branch_id.term_conditions1
    
    warehouse_id = fields.Many2one(
        'stock.warehouse', 'Warehouse',
        default=lambda self: self._get_default_warehouse()
    )
    style = fields.Many2one(
        'report.template.settings',
        'Invoice Style',
        help="Select Style to use when printing this invoice",
        default=_get_default_template)

    responsable_branch = fields.Boolean(string="Responsable Branch", compute='_compute_is_responsable')

    @api.depends_context('uid')
    def _compute_is_responsable(self):
        for rec in self:
            rec.responsable_branch = rec._is_responsable()

    @api.model
    def _is_responsable(self):
        # return self.env.user.has_group('gts_branch_management.group_branch_user_manager')
        return True

    @api.model
    def _get_default_warehouse(self):
        Warehouse = self.env['stock.warehouse'].sudo()
        branch = self.env.user.branch_id
        if branch and Warehouse._fields.get('branch_id'):
            try:
                return Warehouse.search([('branch_id', '=', branch.id)], limit=1)
            except Exception:
                self.env.cr.rollback()
        return Warehouse.search([], limit=1)

    @api.onchange('branch_id')
    def change_report_style(self):
        if self.branch_id:
            template = self.env['report.template.settings'].search([('branch_id', '=', self.branch_id.id)])
            self.style = template.id
        else:
            self.style = False


    @api.onchange('branch_id')
    def change_journal(self):
        if self.branch_id:
            inv_type = self.move_type
            if inv_type in ('in_invoice', 'in_refund'):
                journal_id = self.branch_id.purchase_journal_id
            elif inv_type == 'entry':
                # Asientos contables: diario tipo general (p. ej. Operaciones misceláneas)
                journal_id = self._search_default_journal()
            else:
                journal_default_id = self.env.user.journal_default_id
                if journal_default_id:
                    journal_id = self.env.user.journal_default_id
                else:
                    journal_id = self.branch_id.journal_id
            if not journal_id:
                raise UserError(_("Please configure journals for selected branch."))
            self.journal_id = journal_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            move_type = vals.get('move_type', self.env.context.get('default_move_type'))
            if move_type == 'entry':
                vals['gts_no_exigir_sucursal'] = False
        moves = super().create(vals_list)
        # Respetar `_get_valid_journal_types` (extendido por gn_banks para
        # admitir bank/cash en entries con `sequence_generated=True`). De lo
        # contrario, este write sobre `journal_id` colisiona con el nombre ya
        # asignado por la secuencia del cheque/transferencia y dispara
        # "No puede editar el diario...".
        entry_bad_journal = moves.filtered(
            lambda m: m.move_type == 'entry'
            and m.journal_id
            and m.journal_id.type not in m._get_valid_journal_types()
        )
        for move in entry_bad_journal:
            move.write({'journal_id': move._search_default_journal().id})
        for move in moves:
            if move.branch_id:
                move.line_ids.with_context(check_move_validity=False).write({'branch_id': move.branch_id.id})
        return moves

    def write(self, vals):
        res = super().write(vals)
        if 'branch_id' in vals:
            for move in self.filtered('branch_id'):
                move.line_ids.with_context(check_move_validity=False).write({'branch_id': move.branch_id.id})
        return res

    def _post(self, soft=True):
        moves = super()._post(soft=soft)
        for move in moves.filtered('branch_id'):
            move.line_ids.with_context(check_move_validity=False).write({'branch_id': move.branch_id.id})
        return moves
