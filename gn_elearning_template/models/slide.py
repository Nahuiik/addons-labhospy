import base64
import io
import mimetypes
import re
import zipfile
from pathlib import PurePosixPath

from lxml import etree, html as lh

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html_sanitize


class SlideChannelSlide(models.Model):
    _inherit = "slide.slide"

    html_template_zip = fields.Binary(
        string="ZIP de plantilla HTML",
        attachment=False,
        help="Carga un archivo ZIP temporal que será procesado para generar el contenido del artículo.",
    )
    html_template_filename = fields.Char(string="Nombre del ZIP")

    _HTML_TEMPLATE_MAX_BYTES = 25 * 1024 * 1024  # 25 MB
    _ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".svg", ".webp"}

    def action_open_import_wizard(self):
        self.ensure_one()
        self._ensure_user_can_import()
        return {
            "type": "ir.actions.act_window",
            "name": _("Importar plantilla HTML"),
            "res_model": "elearning.html.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_slide_id": self.id,
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        pending_imports = []
        for vals in vals_list:
            zip_binary = vals.pop("html_template_zip", False)
            filename = vals.pop("html_template_filename", False)
            pending_imports.append((zip_binary, filename))
        records = super().create(vals_list)
        for slide, (zip_binary, filename) in zip(records, pending_imports):
            if zip_binary and slide.slide_type == "article":
                slide.import_html_template(zip_binary, filename)
        return records

    def write(self, vals):
        zip_binary = vals.pop("html_template_zip", False)
        filename = vals.pop("html_template_filename", False)
        res = super().write(vals)
        if (
            zip_binary
            and not self.env.context.get("html_template_skip_import")
            and any(slide.slide_type == "article" for slide in self)
        ):
            for slide in self:
                if slide.slide_type != "article":
                    continue
                slide.import_html_template(zip_binary, filename)
        return res

    def _ensure_user_can_import(self):
        if not (
            self.env.user.has_group("website_slides.group_website_slides_officer")
            or self.env.user.has_group("website_slides.group_website_slides_manager")
        ):
            raise UserError(_("Solo instructores o administradores de eLearning pueden importar plantillas."))

    def import_html_template(self, zip_binary, filename=None):
        self.ensure_one()
        self._ensure_user_can_import()
        if self.slide_type != "article":
            raise ValidationError(_("La importación solo está disponible para contenidos de tipo Artículo."))
        if not zip_binary:
            raise ValidationError(_("Debes proporcionar un archivo ZIP válido."))
        if filename and not filename.lower().endswith(".zip"):
            raise ValidationError(_("El archivo debe tener extensión .zip."))
        raw_data = base64.b64decode(zip_binary)
        if len(raw_data) > self._HTML_TEMPLATE_MAX_BYTES:
            raise ValidationError(_("El archivo ZIP no puede superar los 25 MB."))
        buffer = io.BytesIO(raw_data)
        if not zipfile.is_zipfile(buffer):
            raise ValidationError(_("El archivo proporcionado no es un ZIP válido."))
        buffer.seek(0)
        with zipfile.ZipFile(buffer) as archive:
            file_infos = [info for info in archive.infolist() if not info.is_dir()]
            if not file_infos:
                raise ValidationError(_("El ZIP está vacío."))
            relative_map = self._prepare_relative_paths(file_infos)
            html_bytes = None
            image_payloads = {}
            css_payloads = []
            js_payloads = []
            for info in file_infos:
                rel_path = relative_map.get(self._clean_zip_name(info.filename))
                if not rel_path:
                    continue
                normalized_path = rel_path.lower()
                content = archive.read(info.filename)
                if normalized_path == "index.html":
                    html_bytes = content
                    continue
                if normalized_path.startswith("images/"):
                    self._validate_image_extension(rel_path)
                    image_payloads[rel_path] = content
                    continue
                if normalized_path.startswith("assets/"):
                    ext = PurePosixPath(rel_path).suffix.lower()
                    if ext == ".css":
                        css_payloads.append((rel_path, content))
                    elif ext == ".js":
                        js_payloads.append((rel_path, content))
                    continue
            if not html_bytes:
                raise ValidationError(_("El ZIP debe contener un archivo index.html en la raíz."))
            html_text = self._decode_html_bytes(html_bytes)
            sanitized_html = html_sanitize(html_text)
            document = self._ensure_html_document(sanitized_html)
            self._strip_unsupported_assets(document)
            image_attachments = self._create_image_attachments(image_payloads)
            self._rewrite_image_sources(document, image_attachments)
            css_blocks = self._prepare_css_blocks(css_payloads, image_attachments)
            self._inject_css(document, css_blocks)
            js_attachments = self._create_js_attachments(js_payloads)
            self._inject_js(document, js_attachments)
            final_html = self._serialize_document(document)
            self._write_imported_content(final_html)

    def _prepare_relative_paths(self, file_infos):
        sanitized = [(info, PurePosixPath(self._clean_zip_name(info.filename))) for info in file_infos]
        meaningful_paths = [path for _, path in sanitized if len(path.parts) > 1]
        prefix_candidates = {p.parts[0] for p in meaningful_paths}
        root_prefix = prefix_candidates.pop() if len(prefix_candidates) == 1 else None
        mapping = {}
        for info, path in sanitized:
            if not path.parts:
                continue
            parts = list(path.parts)
            if root_prefix and len(parts) > 1 and parts[0] == root_prefix:
                parts = parts[1:]
            rel_path = "/".join(parts)
            mapping[self._clean_zip_name(info.filename)] = rel_path
        return mapping

    def _decode_html_bytes(self, html_bytes):
        for encoding in ("utf-8", "latin-1"):
            try:
                return html_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValidationError(_("No se pudo decodificar el archivo index.html (UTF-8 o Latin-1)."))

    def _ensure_html_document(self, html_text):
        document = None
        for parser in (
            getattr(lh, "document_fromstring", None),
            getattr(lh, "fromstring", None),
            getattr(lh, "fragment_fromstring", None),
        ):
            if parser is None:
                continue
            try:
                document = parser(html_text)
                if document is not None:
                    break
            except Exception:
                continue
        if document is None:
            try:
                document = etree.HTML(html_text)
            except Exception:
                document = None
        if document is None or document.tag.lower() != "html":
            document = etree.HTML("<html><head/><body/></html>")
        head = document.find("head")
        if head is None:
            head = etree.SubElement(document, "head")
        body = document.find("body")
        if body is None:
            body = etree.SubElement(document, "body")
        return document

    def _serialize_document(self, document):
        """Compile head/body content into a fragment suitable for Html fields."""
        if document is None:
            return ""

        def _collect(node):
            chunks = []
            if node.text:
                chunks.append(node.text)
            for child in node:
                chunks.append(lh.tostring(child, encoding="unicode", method="html"))
                if child.tail:
                    chunks.append(child.tail)
            return "".join(chunks)

        fragments = []
        head = document.find("head")
        if head is not None:
            fragments.append(_collect(head))
        body = document.find("body")
        if body is not None:
            fragments.append(_collect(body))
        if not fragments:
            fragments.append(lh.tostring(document, encoding="unicode", method="html"))
        return "".join(fragments)

    def _validate_image_extension(self, rel_path):
        extension = PurePosixPath(rel_path).suffix.lower()
        if extension not in self._ALLOWED_IMAGE_EXTENSIONS:
            raise ValidationError(
                _(
                    "Formato de imagen no soportado en '%(path)s'. Usa JPG, PNG, SVG o WEBP.",
                    path=rel_path,
                )
            )

    def _create_image_attachments(self, payloads):
        Attachment = self.env["ir.attachment"].sudo()
        attachments = {}
        for rel_path, content in payloads.items():
            attachment = Attachment.create(
                {
                    "name": PurePosixPath(rel_path).name,
                    "datas": base64.b64encode(content),
                    "res_model": self._name,
                    "res_id": self.id,
                    "mimetype": mimetypes.guess_type(rel_path)[0] or "application/octet-stream",
                    "public": True,
                }
            )
            attachments[rel_path] = attachment
        return attachments

    def _rewrite_image_sources(self, document, attachments):
        for img in document.xpath(".//img[@src]"):
            src = img.get("src") or ""
            normalized = self._normalize_reference(src)
            attachment = attachments.get(normalized)
            if attachment:
                img.set("src", f"/web/image/{attachment.id}")

    def _strip_unsupported_assets(self, document):
        """Drop asset declarations that reference unavailable website bundles."""
        if document is None:
            return
        def should_remove(value):
            if not value:
                return False
            lowered = value.lower()
            return "website.website_builder_assets" in lowered or "/web/assets/" in lowered

        for link in document.xpath(".//link[@href]"):
            if should_remove(link.get("href")):
                parent = link.getparent()
                if parent is not None:
                    parent.remove(link)

        for script in document.xpath(".//script[@src]"):
            if should_remove(script.get("src")):
                parent = script.getparent()
                if parent is not None:
                    parent.remove(script)

        for asset_node in document.xpath(".//*[@t-call-assets]"):
            target = (asset_node.get("t-call-assets") or "").strip()
            if should_remove(target):
                parent = asset_node.getparent()
                if parent is not None:
                    parent.remove(asset_node)

    def _prepare_css_blocks(self, css_payloads, image_attachments):
        css_blocks = []
        for _, content in css_payloads:
            css_text = self._decode_css_bytes(content)
            rewritten = self._rewrite_css_urls(css_text, image_attachments)
            css_blocks.append(rewritten)
        return css_blocks

    def _decode_css_bytes(self, css_bytes):
        for encoding in ("utf-8", "latin-1"):
            try:
                return css_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValidationError(_("No se pudo decodificar un archivo CSS (UTF-8 o Latin-1)."))

    def _rewrite_css_urls(self, css_text, image_attachments):
        if not css_text:
            return css_text

        def replace(match):
            raw = match.group(1)
            if not raw:
                return match.group(0)
            ref = raw.strip(" '\"")
            lower = ref.lower()
            if lower.startswith(("http://", "https://", "data:")):
                return match.group(0)
            normalized = self._normalize_reference(ref)
            attachment = image_attachments.get(normalized)
            if not attachment:
                return match.group(0)
            return f"url('/web/image/{attachment.id}')"

        return re.sub(r"url\(([^)]+)\)", replace, css_text, flags=re.IGNORECASE)

    def _inject_css(self, document, css_blocks):
        if not css_blocks:
            return
        head = document.find("head")
        if head is None:
            head = etree.SubElement(document, "head")
        for css_text in css_blocks:
            style = etree.SubElement(head, "style", type="text/css", **{"data-gn-template": "1"})
            style.text = css_text

    def _create_js_attachments(self, js_payloads):
        Attachment = self.env["ir.attachment"].sudo()
        created = []
        for rel_path, content in js_payloads:
            attachment = Attachment.create(
                {
                    "name": PurePosixPath(rel_path).name,
                    "datas": base64.b64encode(content),
                    "res_model": self._name,
                    "res_id": self.id,
                    "mimetype": mimetypes.guess_type(rel_path)[0] or "application/octet-stream",
                    "public": True,
                }
            )
            created.append(attachment)
        return created

    def _inject_js(self, document, js_attachments):
        if not js_attachments:
            return
        head = document.find("head")
        if head is None:
            head = etree.SubElement(document, "head")
        for attachment in js_attachments:
            script = etree.SubElement(
                head,
                "script",
                type="text/javascript",
                src=f"/web/content/{attachment.id}",
            )
            script.set("defer", "defer")

    def _write_imported_content(self, html_value):
        self.ensure_one()
        html_fields = [name for name, field in self._fields.items() if field.type == "html"]
        if not html_fields:
            raise UserError(_("No se encontró un campo HTML para almacenar el contenido importado."))
        preferred = [name for name in ("description", "content") if name in html_fields]
        target_fields = preferred or html_fields
        values = {field_name: html_value for field_name in target_fields}
        super(SlideChannelSlide, self.with_context(html_template_skip_import=True)).write(values)

    def _normalize_reference(self, reference):
        if not reference:
            return reference
        ref = reference.split("?")[0].split("#")[0]
        normalized = PurePosixPath(ref.strip("./"))
        return "/".join(normalized.parts)

    def _clean_zip_name(self, name):
        normalized = (name or "").replace("\\", "/").strip("/")
        if not normalized:
            return ""
        return "/".join(PurePosixPath(normalized).parts)
