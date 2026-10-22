# -*- coding: utf-8 -*-
"""Marca en informes QWeb: logo de res.company y paleta derivada del logo."""
import base64
import io
import logging
from collections import Counter

_logger = logging.getLogger(__name__)

# Valores por defecto (misma línea que el tema fijo anterior)
_DEFAULT_CSS = (
    '--nh-accent:#000000;--nh-heading:#4d4d4d;--nh-muted:#808080;--nh-ink:#1a1a1a;'
    '--nh-row-alt:#f4f4f4;--nh-totals-bg:#e8e8e8;--nh-border:#cccccc'
)


def _lum(rgb):
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def _rgb_hex(rgb):
    r, g, b = (max(0, min(255, int(c))) for c in rgb)
    return '#%02x%02x%02x' % (r, g, b)


def _mix(a, b, t):
    """t=1 → b."""
    return tuple(int(a[i] * (1.0 - t) + b[i] * t) for i in range(3))


def _quantize(c, step=24):
    return tuple(min(255, (x // step) * step) for x in c)


def _guess_mime_b64(b64_str):
    try:
        raw = base64.b64decode(b64_str)
    except Exception:
        return 'image/png', b''
    if raw[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png', raw
    if raw[:2] == b'\xff\xd8':
        return 'image/jpeg', raw
    if raw[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif', raw
    if raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
        return 'image/webp', raw
    return 'image/png', raw


def _logo_field_to_b64(logo):
    if not logo:
        return None
    if isinstance(logo, memoryview):
        logo = logo.tobytes()
    if isinstance(logo, bytes):
        try:
            return base64.b64encode(logo).decode('ascii')
        except Exception:
            return None
    if isinstance(logo, str):
        return logo
    return None


def company_logo_data_uri(company):
    """Data URI del logo (PDF/HTML) tomando los campos estándar de Odoo.

    Orden: ``logo_web``, ``logo`` (relacionado con imagen del contacto de la
    compañía), y por último ``image_1920`` del partner si hiciera falta.
    Con WebP intenta conversión a PNG para wkhtmltopdf.
    """
    company = company.sudo()

    def _try_uri_from_b64(logo_b64):
        if not logo_b64:
            return None
        logo_b64 = ''.join(logo_b64.split())
        try:
            mime, raw = _guess_mime_b64(logo_b64)
        except Exception:
            return None
        if not raw:
            return None
        if mime == 'image/webp':
            try:
                from PIL import Image
                im = Image.open(io.BytesIO(raw))
                if im.mode not in ('RGB', 'RGBA'):
                    im = im.convert('RGBA')
                out = io.BytesIO()
                im.save(out, format='PNG')
                png_b64 = base64.b64encode(out.getvalue()).decode('ascii')
                return 'data:image/png;base64,%s' % png_b64
            except Exception:
                pass
        return 'data:%s;base64,%s' % (mime, logo_b64)

    streams = [
        company.logo_web,
        company.logo,
    ]
    partner = company.partner_id.sudo() if company.partner_id else None
    if partner:
        streams.append(partner.image_1920)

    for raw_logo in streams:
        uri = _try_uri_from_b64(_logo_field_to_b64(raw_logo))
        if uri:
            return uri
    return False


def _palette_from_logo_b64(logo_b64):
    """Hex CSS variables a partir del binario del logo."""
    logo_b64 = ''.join(logo_b64.split())
    try:
        from PIL import Image
    except ImportError:
        _logger.debug('PIL no disponible; se usan colores por defecto en informes.')
        return None
    try:
        raw = base64.b64decode(logo_b64)
        im = Image.open(io.BytesIO(raw)).convert('RGB')
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.LANCZOS
        im = im.resize((48, 48), resample)
        pixels = [im.getpixel((x, y)) for x in range(im.width) for y in range(im.height)]
    except Exception as exc:
        _logger.debug('No se pudo analizar el logo para la paleta: %s', exc)
        return None

    darkish = [p for p in pixels if _lum(p) < 195]
    sample = darkish if len(darkish) > len(pixels) * 0.03 else pixels
    quantized = [_quantize(p, 28) for p in sample]
    if not quantized:
        return None
    accent = Counter(quantized).most_common(1)[0][0]

    if _lum(accent) > 115:
        accent = tuple(int(c * 0.55) for c in accent)
    if _lum(accent) > 95:
        accent = tuple(max(0, int(c * 0.72)) for c in accent)

    heading = _mix(accent, (20, 20, 20), 0.35)
    if _lum(heading) > 90:
        heading = _mix(heading, (0, 0, 0), 0.45)

    muted = _mix(accent, (128, 128, 128), 0.5)
    ink = _mix(accent, (26, 26, 26), 0.25)
    row_alt = _mix((255, 255, 255), accent, 0.06)
    totals_bg = _mix((255, 255, 255), accent, 0.18)
    border = _mix((204, 204, 204), accent, 0.22)

    return {
        'accent': _rgb_hex(accent),
        'heading': _rgb_hex(heading),
        'muted': _rgb_hex(muted),
        'ink': _rgb_hex(ink),
        'row_alt': _rgb_hex(row_alt),
        'totals_bg': _rgb_hex(totals_bg),
        'border': _rgb_hex(border),
    }


def _report_public_base_url(company):
    """URL pública del sitio (suele coincidir con la barra de dirección del usuario)."""
    try:
        from odoo.http import request
        if request and getattr(request, 'httprequest', None):
            return request.httprequest.url_root.rstrip('/')
    except RuntimeError:
        pass
    return (company.get_base_url() or '').rstrip('/')


def _nh_report_branding_tail(company, logo_src, report_logo_http_src, style):
    """Ruta propia: /web/binary/company_logo solo usa logo_web; el informe puede usar logo/contacto."""
    base = _report_public_base_url(company)
    rel = '/web/binary/hn_company_report_logo?company=%s' % company.id
    hn_http = ('%s%s' % (base, rel)) if base else False
    nh_logo = logo_src or hn_http or report_logo_http_src
    return {
        'report_logo_src': logo_src,
        'report_logo_http_src': report_logo_http_src,
        'report_hn_logo_http_src': hn_http,
        'report_logo_relative_src': rel,
        'nh_report_logo_src': nh_logo,
        'report_branding_style': style,
    }


def company_report_branding(company):
    """
    Claves para QWeb:
    - report_logo_src: data URI si se pudo construir
    - report_logo_http_src: URL absoluta /web/binary/company_logo (solo logo_web)
    - nh_report_logo_src: data URI o URL a /web/binary/hn_company_report_logo (logo_web, logo, contacto)
    - report_branding_style: atributo style con variables --nh-*
    """
    company = company.sudo()
    logo_src = company_logo_data_uri(company)
    base = (company.get_base_url() or '').rstrip('/')
    report_logo_http_src = False
    if base and company.id:
        report_logo_http_src = '%s/web/binary/company_logo?company=%s' % (base, company.id)

    uses_default = bool(getattr(company, 'uses_default_logo', False))
    logo_b64 = _logo_field_to_b64(company.logo)
    if not logo_b64 and company.partner_id:
        logo_b64 = _logo_field_to_b64(company.partner_id.sudo().image_1920)

    if uses_default or not logo_b64:
        return _nh_report_branding_tail(company, logo_src, report_logo_http_src, _DEFAULT_CSS)

    palette = _palette_from_logo_b64(logo_b64)
    if not palette:
        return _nh_report_branding_tail(company, logo_src, report_logo_http_src, _DEFAULT_CSS)
    style = ';'.join(
        [
            '--nh-accent:%s' % palette['accent'],
            '--nh-heading:%s' % palette['heading'],
            '--nh-muted:%s' % palette['muted'],
            '--nh-ink:%s' % palette['ink'],
            '--nh-row-alt:%s' % palette['row_alt'],
            '--nh-totals-bg:%s' % palette['totals_bg'],
            '--nh-border:%s' % palette['border'],
        ]
    )
    return _nh_report_branding_tail(company, logo_src, report_logo_http_src, style)
