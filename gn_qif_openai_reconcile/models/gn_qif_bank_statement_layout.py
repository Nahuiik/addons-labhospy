# -*- coding: utf-8 -*-
from odoo import fields, models


class GnQifBankStatementLayout(models.Model):
    """Definición de layout por formato de archivo (notas IA y documentación por banco)."""

    _name = 'gn.qif.bank.statement.layout'
    _description = 'Layout extracto por banco (importador IA)'
    _order = 'sequence, name'

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True)

    file_format_key = fields.Char(
        string='Clave técnica de formato',
        required=True,
        index=True,
        help='Valor interno igual al formato detectado (p. ej. xlsx_atlantida, xls_ficohsa). '
             'Debe coincidir con `file_format` del asistente QIF/OpenAI cuando aplique.',
    )

    specification = fields.Html(
        string='Columnas / estructura',
        help='Resumen técnico de filas/columnas y convenciones (importe = crédito − débito, etc.).',
    )

    ai_context = fields.Text(
        string='Contexto para IA',
        help='Texto plano añadido al prompt de OpenAI al analizar movimientos con este formato. '
             'Use para políticas específicas (ACH, ISR, nomenclatura de refs).',
    )

    notes = fields.Text(string='Notas internas')

    _code_unique = models.Constraint('unique(code)', 'El código de layout debe ser único.')
