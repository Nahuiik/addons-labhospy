# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class FicohsaPosImportHistory(models.Model):
    """Una fila por ejecución exitosa del asistente de importación FICOHSA POS."""

    _name = "ficohsa.pos.import.history"
    _description = "Historial de importaciones FICOHSA POS"
    _order = "id desc"

    name = fields.Char(string="Referencia", required=True)
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Usuario",
        required=True,
        default=lambda self: self.env.user,
    )
    import_mode = fields.Selection(
        [
            ("single", "Un solo archivo"),
            ("batch", "Por lotes (varios Excel)"),
        ],
        string="Modo",
        required=True,
    )
    bank_journal_id = fields.Many2one(
        "account.journal",
        string="Diario banco depósito",
        domain=[("type", "=", "bank")],
    )
    file_count = fields.Integer(string="Archivos procesados", readonly=True)
    files_summary = fields.Text(string="Nombres de archivo", readonly=True)
    liquidaciones_creadas = fields.Integer(
        string="Liquidaciones creadas",
        readonly=True,
        help="Nuevos documentos debit.credit validados.",
    )
    operaciones_previstas = fields.Integer(
        string="Operaciones día/archivo",
        readonly=True,
        help="Filas día × archivo con importe antes de omitir duplicados.",
    )
    result_message = fields.Text(string="Resumen", readonly=True)
    log_line_ids = fields.One2many(
        "ficohsa.pos.import.file.log",
        "history_id",
        string="Archivos (huella)",
    )

    @api.model
    def create_from_wizard(
        self,
        import_mode,
        bank_journal,
        file_entries,
        liquidaciones_creadas,
        operaciones_previstas,
        result_message,
        files_summary,
    ):
        """Llamado al final de una importación correcta."""
        lbl_mode = _("lote") if import_mode == "batch" else _("un archivo")
        name = _("Importación FICOHSA POS (%s)") % lbl_mode
        return self.create(
            {
                "name": name,
                "company_id": self.env.company.id,
                "user_id": self.env.user.id,
                "import_mode": import_mode,
                "bank_journal_id": bank_journal.id if bank_journal else False,
                "file_count": len(file_entries),
                "files_summary": files_summary,
                "liquidaciones_creadas": liquidaciones_creadas,
                "operaciones_previstas": operaciones_previstas,
                "result_message": result_message,
            }
        )
