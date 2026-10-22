from odoo import _, fields, models
from odoo.exceptions import ValidationError


class ElearningHtmlImportWizard(models.TransientModel):
    _name = "elearning.html.import.wizard"
    _description = "Importador de plantillas HTML eLearning"

    upload_file = fields.Binary(
        string="Archivo ZIP",
        required=True,
        attachment=False,
        help="Archivo ZIP con index.html, carpeta images/ y opcionalmente assets/.",
    )
    file_name = fields.Char(string="Nombre del archivo", required=True)
    slide_id = fields.Many2one(
        "slide.slide",
        string="Artículo",
        required=True,
        readonly=True,
    )

    def action_import_template(self):
        self.ensure_one()
        if not self.upload_file:
            raise ValidationError(_("Debes seleccionar un archivo ZIP."))
        self.slide_id.import_html_template(self.upload_file, self.file_name)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Importación completada"),
                "message": _("Plantilla HTML importada correctamente. Verifica el contenido en vista previa."),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
