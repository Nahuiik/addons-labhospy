#!/usr/bin/env python3
"""Rellena el PDF de Elite Architects con datos técnicos de LABHOSPY."""
from pathlib import Path

from pypdf import PdfReader, PdfWriter

SRC = Path(
    "/home/odoo/src/labhospy/"
    "Odoo_Labhospy_Access_and_Integration_Requirements_-_Elite_Architects_Oct6_26 (1).pdf"
)
OUT_PDF = Path(
    "/home/odoo/src/labhospy/"
    "Odoo_Labhospy_Access_and_Integration_Requirements_-_FILLED.pdf"
)

# Sección 1: contactos Nauiik — completar nombres/WhatsApp con el equipo interno.
ANSWERS = {
    "ans_1": (
        "[COMPLETAR] Líder de cuenta — WhatsApp — email "
        "(sugerencia coordinación: info@gruponahuiik.com)"
    ),
    "ans_2": (
        "[COMPLETAR] Consultor funcional Odoo (Ventas/Compras/Inventario/Contabilidad) "
        "— WhatsApp — email"
    ),
    "ans_3": (
        "[COMPLETAR] Líder técnico / desarrollo (usuarios, grupos, API, campos custom) "
        "— WhatsApp — email"
    ),
    "ans_4": (
        "[COMPLETAR] Administrador servidor/hosting (backups, seguridad, firewall) "
        "— WhatsApp — email (infra: gncs.io)"
    ),
    "ans_5": (
        "[COMPLETAR] Contacto escalamiento urgencias — WhatsApp — email"
    ),
    "ans_6": "Odoo 19.0 — Community (sin módulo web_enterprise).",
    "ans_7": (
        "Servidor del partner local (hosting GNCS), no Odoo Online ni Odoo.sh. "
        "Acceso vía HTTPS público."
    ),
    "ans_8": "URL: https://labhospy.gncs.io — Base de datos: LABHOSPY",
    "ans_9": (
        "Instaladas: Ventas (sale), CRM, Compras (purchase), Inventario (stock), "
        "Contabilidad (account). App estándar «Commissions» no instalada."
    ),
    "ans_10": (
        "1 compañía: LABORATORIES AND HOSPITAL SUPPLY, S. DE.R.L. DE C.V — moneda HNL. "
        "Sucursales (gts_branch): Oficina Principal, Sucursal Lomas, Sucursal San Pedro Sula."
    ),
    "ans_11": (
        "Licitaciones/sector público: etiqueta de contacto «Publico» en res.partner.category "
        "(clientes «Privado»/«privado» para sector privado). Equipo de ventas: crm.team «Ventas». "
        "CRM: etapas Nuevo → Calificado → Propuesta → Ganado."
    ),
    "ans_12": (
        "Ventas: sale.order.user_id (vendedor); gn_labhospy_immediate_payment. "
        "Líneas: gn_labhospy_supplier_id, catalog_code, productos controlados. "
        "Compras/import: purchase.order.gn_labhospy_compra_internacional; "
        "account.move.is_of_import / gn_labhospy_es_importacion. "
        "Comisiones POS/tarjetas: gn_payment_extra en account.payment (no matriz comercial en Odoo)."
    ),
    "ans_13": (
        "Vendedor Odoo = sale.order.user_id. Principales (2025+): Leocadio Barahona (leob@labhospy.hn), "
        "Karla George (karlag@labhospy.hn), Marcela Garcia (tiendatgu@labhospy.hn), Gabriel Lopez "
        "(oficial1tgu@labhospy.hn), Milton Canaca (oficial2tgu@labhospy.hn). "
        "Lista completa vendedores NOUVA pendiente de cruce."
    ),
    "ans_14": (
        "Operación y soporte Odoo: Grupo Nahuiik (Nauiik). Infraestructura/hosting: GNCS (gncs.io). "
        "Backups y parches según contrato de hosting; bitácoras de acceso vía servidor/proxy."
    ),
    "ans_15": (
        "Sin lista blanca de IP documentada en Odoo. Acceso web HTTPS. "
        "Si EA requiere allow-list, coordinar con GNCS/Nauiik para agregar IPs del integrador."
    ),
    "ans_16": (
        "Últimos 12 meses (desde 2025-10-11): OV activas 4,286; facturas cliente publicadas 3,416; "
        "OC 476; clientes (customer_rank>0) 1,275; productos 1,613."
    ),
    "ans_17": (
        "Diarios tipo banco (account.journal, type=bank): cuentas operativas HNL/USD/EUR — "
        "Banpaís, Occidente, Atlántida, BAC, Ficohsa, Davivienda; cajas TGU/SPS/Lomas; POS; "
        "anticipos proveedores local/int.; tarjeta corp. Banpaís. Detalle en Excel adjunto."
    ),
    "ans_18": (
        "Ventas brutas baseline: suma amount_untaxed_signed de account.move posted "
        "move_type=out_invoice menos out_refund, invoice_date en ventana 12 meses "
        "(ej. 3,408 FC ≈ 20.34M HNL neto antes imp.; 8 NC ≈ -56K HNL). Confirmar con Contabilidad."
    ),
    "ans_19": (
        "CRM: Nuevo, Calificado, Propuesta, Ganado. Cotizaciones/Pedidos: draft=Quotation, "
        "sent=Quotation Sent, sale=Sales Order, cancel=Cancelled."
    ),
    "ans_20": (
        "No hay app Odoo Commissions ni matriz de comisiones de ventas en ERP. "
        "Comisiones bancarias/POS en gn_payment_extra (account.payment: commission_percentage, "
        "convenios tarjeta). Comisiones comerciales: fuera de Odoo o por confirmar con Gestión."
    ),
    "ans_21": (
        "PO internacional: purchase.order.gn_labhospy_compra_internacional=True; moneda proveedor "
        "en currency_id; plazos payment_term_id. Factura: is_of_import / gn_labhospy_es_importacion; "
        "costos en destino vía gn_import_landed_cost si aplica. Seguimiento SC en recepciones controladas."
    ),
}

# Checklist: comentarios (máx. 300) y estado ENTREGADO/PENDIENTE
CHECKLIST = {
    1: ("Tabla contactos Nauiik: pendiente nombres/WhatsApp internos.", "p"),
    2: ("Versión 19 Community y apps principales documentadas.", "e"),
    3: ("Hosting partner GNCS (no Online/sh).", "e"),
    4: ("URL labhospy.gncs.io, BD LABHOSPY.", "e"),
    5: ("Sales, CRM, Purchase, Stock, Accounting.", "e"),
    6: ("1 compañía HNL + 3 sucursales.", "e"),
    7: ("Etiqueta contacto Publico/Privado + equipo Ventas.", "e"),
    8: ("Campos gn_labhospy y comisiones POS documentados.", "e"),
    9: ("Mapeo parcial user_id; lista NOUVA pendiente.", "p"),
    10: ("Nauiik + GNCS; detalle backups a confirmar en reunión.", "p"),
    11: ("Allow-list IP: no aplica hoy; abrir si EA lo pide.", "p"),
    12: ("Usuario AI Agents – Elite Architects: no creado aún.", "p"),
    13: ("Grupo AI Agents – Read Only: no creado aún.", "p"),
    14: ("API key: pendiente tras crear usuario.", "p"),
    15: ("BD prueba/staging: pendiente provisionar.", "p"),
    16: ("Compromiso 5 días hábiles: aceptado por Nauiik al entregar.", "p"),
    17: ("Conteos 12 meses entregados en cuestionario.", "e"),
    18: ("Mapa diarios banco: resumen en PDF; detalle en Excel.", "e"),
    19: ("Definición ventas brutas vía FC/NC publicadas.", "e"),
    20: ("Etapas CRM y estados cotización documentados.", "e"),
    21: ("Sin matriz comisiones ventas en Odoo.", "e"),
    22: ("Importación vía flags PO/factura y módulos GN.", "e"),
    23: ("Mapa de datos: pendiente revisión conjunta EA.", "p"),
    24: ("Estabilidad 7 días: pendiente tras go-live integración.", "p"),
    25: ("Grupo Sales Drafts: no aplica fase Ghost.", "p"),
    26: ("Prueba aprobación/rollback cotizaciones: fase posterior.", "p"),
}


def main():
    reader = PdfReader(str(SRC))
    writer = PdfWriter()
    writer.append(reader)

    fields = {**ANSWERS}
    for idx, (comment, status) in CHECKLIST.items():
        fields[f"od_c{idx}"] = comment[:300]
        if status == "e":
            fields[f"od_e{idx}"] = "/Yes"
            fields[f"od_p{idx}"] = "/Off"
        else:
            fields[f"od_e{idx}"] = "/Off"
            fields[f"od_p{idx}"] = "/Yes"

    for page in writer.pages:
        writer.update_page_form_field_values(page, fields, auto_regenerate=False)

    with open(OUT_PDF, "wb") as f:
        writer.write(f)
    print(f"Written {OUT_PDF}")


if __name__ == "__main__":
    main()
