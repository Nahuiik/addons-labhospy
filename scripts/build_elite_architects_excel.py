#!/usr/bin/env python3
"""Genera Excel con respuestas completas (secciones 2.1 y 3) para Elite Architects."""

# Métricas LABHOSPY — actualizar al regenerar (ventana: últimos 12 meses desde fecha de corte).
METRICS_CUTOFF = "2026-10-12"
METRICS_SINCE = "2025-10-12"
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
OUT = Path(
    "/home/odoo/src/labhospy/"
    "Odoo_Labhospy_Access_and_Integration_Requirements_-_RESPUESTAS.xlsx"
)

SECTION_21 = [
    (
        1,
        "ans_6",
        "Odoo version (16, 17, 18 or 19) and edition (Community or Enterprise)",
        "Versión y edición de Odoo",
        """Odoo 19.0 (serie 19, build Community).
Edición: Community. No está instalado el módulo enterprise web_enterprise ni licencia Enterprise.
Código fuente desplegado desde /home/odoo/src/odoo con addons de proyecto en /home/odoo/src/labhospy.""",
    ),
    (
        2,
        "ans_7",
        "Hosting: Odoo Online, Odoo.sh, or the local partner's server?",
        "Tipo de hosting",
        """Hosting en servidor del partner local (GNCS), no Odoo Online ni Odoo.sh.
Acceso productivo por HTTPS en subdominio dedicado.
API/XML-RPC y JSON-RPC disponibles en la misma URL base (según configuración estándar Odoo).
No aplica requisito de plan Custom de Odoo Online para API.""",
    ),
    (
        3,
        "ans_8",
        "Web address and database name",
        "URL y nombre de base de datos",
        """URL de producción: https://labhospy.gncs.io
Nombre de base de datos PostgreSQL: LABHOSPY
Directorio filestore (referencia despliegue): /home/odoo/data/labhospy""",
    ),
    (
        4,
        "ans_9",
        "Installed apps (Sales, CRM, Purchase, Inventory, Accounting, Commissions)",
        "Aplicaciones instaladas",
        """Aplicaciones estándar relevantes para el proyecto (state=installed):
• Ventas (sale) y sale_stock
• CRM (crm)
• Compras (purchase) y purchase_stock
• Inventario (stock), incl. product_expiry
• Contabilidad (account) y localización Honduras (l10n_hn_*)

App estándar Odoo «Commissions» / sale_commission: NO instalada.

Módulos custom Labhospy relevantes para integración: gn_labhospy, gn_payment_extra,
gn_import_landed_cost, gts_branch_management, l10n_hn_account, gn_accounting_reports, entre otros.""",
    ),
    (
        5,
        "ans_10",
        "Companies and currencies in use",
        "Compañías y monedas",
        """Compañías legales en Odoo: 1
• LABORATORIES AND HOSPITAL SUPPLY, S. DE.R.L. DE C.V (ID 1)
Moneda de la compañía: HNL (Lempira hondureño).

Sucursales operativas (módulo gts_branch_management / res.branch):
• Oficina Principal
• Sucursal Lomas
• Sucursal San Pedro Sula

Monedas extranjeras en operación (compras, bancos, PO): USD y EUR (tipos en res.currency.rate).
Contabilidad y reportes principales en HNL.""",
    ),
    (
        6,
        "ans_11",
        "How tenders are marked in Odoo (sales team, tag, customer type or other)",
        "Cómo se marcan licitaciones / sector público",
        """No existe un campo dedicado «licitación» en sale.order en el código custom revisado.

Práctica en datos de contactos (res.partner):
• Etiqueta/categoría de contacto «Publico» (res.partner.category) para clientes del sector público / licitaciones.
• Etiquetas «Privado» / «privado» para clientes privados.

Equipo de ventas por defecto en pedidos: crm.team «Ventas» (ID 1).

Pipeline CRM (crm.stage): Nuevo → Calificado → Propuesta → Ganado.
Oportunidades CRM usan checklist (gn_crm_checklist: checklist_ids) cuando aplica seguimiento comercial.

Recomendación: validar con Gestión/NOUVA si además usan convenciones en nombre de OV o notas internas.""",
    ),
    (
        7,
        "ans_12",
        "Custom fields we should know about (commission, salesperson, import tracking)",
        "Campos personalizados relevantes",
        """Vendedor / ventas:
• sale.order.user_id — vendedor estándar Odoo (Salesperson).
• sale.order: gn_labhospy_immediate_payment, gn_labhospy_has_invoice, gn_labhospy_has_controlled_products, gn_labhospy_order_contact_display.
• sale.order.line: gn_labhospy_supplier_id, gn_labhospy_catalog_code, gn_labhospy_model, gn_labhospy_is_controlled, gn_labhospy_application_use_id.

Contactos (res.partner): gn_fiscal_discount_percent, gn_is_patient, datos fiscales SAR, etc.

Comisiones:
• No hay matriz de comisiones de ventas en Odoo.
• Comisiones de medios de pago (POS/tarjetas): account.payment en gn_payment_extra (commission_percentage, commission_amount, convenios).

Importación / compras internacionales:
• purchase.order.gn_labhospy_compra_internacional (boolean).
• account.move: is_of_import y gn_labhospy_es_importacion (l10n_hn_account / gn_labhospy).
• Costos en destino: módulo gn_import_landed_cost cuando aplica.
• Productos controlados (sustancias): gn_labhospy_is_controlled en product.template.""",
    ),
    (
        8,
        "ans_13",
        "Odoo user of each seller (NOUVA shares the seller list)",
        "Usuario Odoo de cada vendedor",
        """El vendedor en pedidos y cotizaciones es sale.order.user_id (res.users).

Usuarios internos con permiso de Ventas (sales_team.group_sale_salesman), activos:
• Darwin Maradiaga — dmaradiaga@labhospy.hn
• Elsa Coello — operaciones@labhospy.hn
• Franklin Espinal — contador@labhospy.hn
• Fransis Nicoll Jiron — asistentecontable@labhospy.hn
• GABRIEL ANTONIO LOPEZ ELVIR — oficial1tgu@labhospy.hn
• Gary Gomez — garyg@labhospy.hn
• Johan Blass Rodriguez Flores — johanr@labhospy.hn
• KARLA ELIZABETH GEORGE CANTILLANO — karlag@labhospy.hn
• Leocadio Barahona Sanchez — leob@labhospy.hn
• Marcela Garcia — tiendatgu@labhospy.hn
• Milton Lizandro Canaca — oficial2tgu@labhospy.hn
• Percy Alonso Hernandez Garcia — percyh@labhospy.hn
• Samuel Eduardo Velasquez Sandoval — compras@labhospy.hn
• Silvia Ofelia Coello Zuniga — silviac@labhospy.hn
• Victor Rene Osorto Nuñez — oficialalmacensps@labhospy.hn

Usuarios que aparecen como user_id en OV recientes pero no en la lista anterior (revisar con NOUVA):
• Yuny Hugueth Miranda Martinez — tiendasps01@labhospy.hn
• ISAAC ANTONIO LAGOS FLORES — tiendatgu02@labhospy.hn
• Nathalie Lizeth Rodas Ortez — rliz83858@gmail.com

Cruce definitivo nombre comercial NOUVA ↔ login Odoo: pendiente de validación por NOUVA/Gestión.""",
    ),
    (
        9,
        "ans_14",
        "Who controls the Odoo server and its protection (backups, security updates, access logs)",
        "Control del servidor y protección",
        """Implementación, soporte funcional/técnico Odoo y customizaciones: Grupo Nahuiik (Nauiik), partner Odoo de Labhospy.

Infraestructura (servidor, red, certificado TLS en gncs.io): hosting GNCS.

Responsabilidades típicas:
• Backups de base de datos y filestore: según contrato de hosting (GNCS), con coordinación Nauiik para restauraciones de prueba.
• Actualizaciones de seguridad del SO y servicios: administración del servidor (GNCS).
• Actualizaciones de versión/módulos Odoo: Nauiik, con ventana acordada con Labhospy (compromiso 5 días hábiles ante cambios para integradores).
• Bitácoras de acceso: logs de servidor/proxy web y auditoría estándar Odoo (mail.message / chatter en documentos); no hay SIEM dedicado documentado en aplicación.""",
    ),
    (
        10,
        "ans_15",
        "Is there a firewall or IP allow-list in front of Odoo? (If yes, we send our IPs to be added.)",
        "Firewall / lista blanca de IP",
        """A la fecha de este documento no hay documentada una lista blanca de IP a nivel aplicación Odoo para acceso API.

El sitio es accesible por HTTPS público (https://labhospy.gncs.io).

Si Elite Architects requiere restricción por IP para XML-RPC/JSON-RPC o VPN, debe enviar el rango de IPs de salida de sus agentes para evaluación conjunta Nauiik + GNCS (reglas en firewall/reverse proxy).

Autenticación API: usuario dedicado + API key (a crear según sección 2.2 del documento EA).""",
    ),
]

JOURNALS = [
    (12, "BNK1", "BANPAIS 0115 CHQ", "1010102.01 Banco del Pais Cheques Lps Cta 11-5"),
    (29, "BNK15", "Caja General Lomas", "1010101.03 Caja General Lomas"),
    (30, "BNK16", "Caja General TGU", "1010101.01 Caja General T.G.U."),
    (31, "BNK17", "Caja General SPS", "1010101.02 Caja General S.P.S."),
    (32, "BNK18", "POS FICOHSA", "1010101.10 Pos Banco Ficohsa"),
    (33, "BNK19", "POS ATLANTIDA", "1010101.11 Pos Banco Atlantida"),
    (34, "BNK20", "Caja Chica TGU", "1010101.04 Caja Chica T.G.U."),
    (35, "BNK21", "Caja Chica Lomas", "1010101.06 Caja Chica Lomas"),
    (36, "BNK22", "Caja Chica SPS", "1010101.05 Caja Chica S.P.S."),
    (40, "BNK23", "POS DAVIVIENDA", "1010101.12 Pos Banco Davivienda"),
    (41, "BNK24", "TARJETA DE CREDITO BANPAIS", "2010108.01 Tarjeta De Crédito Corporativa Banpais"),
    (43, "BNK25", "ANTICIPO A PROVEEDORES LOCALES", "1010204.01 Anticipo a proveedores Locales"),
    (47, "BNK26", "ANTICIPO A PROVEEDORES INTERNACIONALES", "1010204.02 Anticipo a proveedores Internacionales"),
    (9, "BNK27", "Operaciones misceláneas", "1010102.03 Banco de Occidente Lps Cta 66-7"),
    (14, "BNK2", "BANPAIS 4313 AHORRO", "1010102.02 Banco del Pais Lps Cta 31-3"),
    (15, "BNK3", "BANCO DE OCCIDENTE 3667 CHQ", "1010102.03 Banco de Occidente Lps Cta 66-7"),
    (16, "BNK4", "BANCO ATLANTIDA 5354", "1010102.04 Banco Atlántida Lps 354"),
    (17, "BNK5", "BAC HONDURAS 8501", "1010102.05 Banco Bac Honduras Lps Cta 501"),
    (18, "BNK6", "BANCO DAVIVIENDA 9202", "1010102.06 Banco Davivienda Lps Cta 202"),
    (19, "BNK7", "BANCO FICOHSA 0977", "1010102.07 Banco Ficohsa Lps Cta 977"),
    (20, "BNK8", "BANPAIS USD 0325", "1010103.01 Banco del Pais USD Cta 32-5"),
    (21, "BNK9", "BANPAIS USD 462-5", "1010103.02 Banco del Pais USD Ahorro Cta 62-5"),
    (22, "BNK10", "BANCO OCCIDENTE USD 41-0", "1010103.04 Banco de Occidente USD Cta 41-0"),
    (23, "BNK11", "BAC HONDURAS USD 361", "1010103.05 Banco Bac Honduras USD Cta 361"),
    (24, "BNK12", "BANCO FICOHSA USD 955", "1010103.06 Banco Ficohsa USD  Cta 955"),
    (25, "BNK13", "BANCO DAVIVIENDA USD 667", "1010103.07 Banco Davivienda USD 667"),
    (26, "BNK14", "BANPAIS EUR 074", "1010103.03 Banco del Pais EUR Cta 667"),
]

SECTION_3 = [
    (
        1,
        "ans_16",
        "Record counts for the last 12 months per main model (sales orders, invoices, "
        "purchase orders, customers, products), to reconcile the history load",
        "Conteos últimos 12 meses por modelo principal",
        f"""Fecha de corte de este reporte: {METRICS_CUTOFF}. Ventana: invoice_date / date_order >= {METRICS_SINCE}.

Modelo Odoo | Criterio | Cantidad
sale.order | date_order >= {METRICS_SINCE}, state != cancel | 4,301
account.move (cliente) | invoice_date >= {METRICS_SINCE}, state=posted, move_type in (out_invoice, out_refund) | 3,420 documentos (3,412 facturas + 8 notas de crédito)
purchase.order | date_order >= {METRICS_SINCE}, state != cancel | 476
res.partner (maestro clientes) | customer_rank > 0 (tamaño actual del maestro) | 1,276
product.product | activos + archivados (maestro actual) | 1,609

Conteos complementarios para reconciliación (actividad en la ventana):
• Clientes con al menos una FC/NC publicada en el período: 1,036
• Productos distintos vendidos en líneas de OV del período: 1,124

Notas para la carga histórica EA (hasta 100,000 registros):
• Usar los mismos dominios al exportar vía API o CSV.
• OV canceladas excluidas del conteo de pedidos; facturas en borrador excluidas (solo posted).
• La carga se planifica fuera de horario laboral según documento EA.""",
    ),
    (
        2,
        "ans_17",
        "Odoo journal each bank account in scope maps to (NOUVA shares the bank account list)",
        "Mapeo cuenta bancaria → diario Odoo",
        f"""En Odoo el saldo en libros por cuenta operativa se consulta vía account.journal (type=bank) y su default_account_id (cuenta 10101xx / 10102xx / 10103xx).

Labhospy tiene {len(JOURNALS)} diarios banco/caja/POS/anticipos configurados. Listado completo en hoja «Diarios_banco» (columnas: ID journal, código, nombre, cuenta contable).

Resumen por tipo:
• Cuentas corrientes/ahorro HNL: Banpaís, Occidente, Atlántida, BAC, Ficohsa, Davivienda
• Cuentas USD y EUR: mismos bancos (diarios BNK8–BNK14)
• Cajas generales y cajas chicas: TGU, SPS, Lomas
• POS bancarios: Ficohsa, Atlántida, Davivienda
• Anticipos a proveedores locales (BNK25) e internacionales (BNK26)
• Tarjeta corporativa Banpaís (BNK24)

Cuentas «en alcance» para el agente CFO: NOUVA debe confirmar el subconjunto operativo; todos los diarios bank del sistema están en Diarios_banco para cruce.

Modelos API útiles: account.journal, account.account, account.bank.statement, account.bank.statement.line.""",
    ),
    (
        3,
        "ans_18",
        "How gross sales can be extracted from Odoo (posted invoices, taxes, credit notes), "
        "so Labhospy can confirm the definition used for the baseline",
        "Extracción de ventas brutas (baseline)",
        f"""Definición propuesta para baseline de ventas brutas (validar con Contabilidad Labhospy):

1) Fuente: account.move con state = posted.
2) Tipos: move_type = out_invoice (facturas cliente) y out_refund (notas de crédito cliente).
3) Fecha: invoice_date dentro de la ventana de 12 meses (>= {METRICS_SINCE}).
4) Monto: suma de amount_untaxed_signed (importe sin impuestos, signo contable; las NC vienen negativas).

Cálculo en ventana actual ({METRICS_SINCE} a {METRICS_CUTOFF}):
• Facturas (out_invoice): 3,412 registros → 20,362,173.81 HNL (amount_untaxed_signed)
• Notas de crédito (out_refund): 8 registros → -56,444.83 HNL
• Ventas netas sin impuestos (FC + NC): 20,305,728.98 HNL

Alternativas si Gestión define «bruto» distinto:
• Con impuestos: usar amount_total_signed en lugar de amount_untaxed_signed.
• Por confirmación comercial: sale.order con state=sale y date_order en ventana (4,301 OV; no coincide con facturación por cortes/credito).
• Informes nativos: account.invoice.report / sale.report (mismos filtros de fecha y estado).

Impuestos Honduras (ISV 15%/18%): en líneas account.move.line con impuestos vinculados; no restar retenciones del «bruto» salvo definición contable explícita.""",
    ),
    (
        4,
        "ans_19",
        "Sales process stages as configured in Odoo (CRM stages and quotation states)",
        "Etapas del proceso de ventas",
        """CRM (crm.lead / oportunidades) — crm.stage configuradas:
1. Nuevo (secuencia 1)
2. Calificado (secuencia 2)
3. Propuesta (secuencia 3)
4. Ganado (secuencia 70)

Seguimiento adicional en CRM: módulo gn_crm_checklist (checklist_ids / checklist_line_ids en crm.lead).

Cotizaciones y pedidos (sale.order) — campo state:
• draft → Quotation (cotización borrador)
• sent → Quotation Sent (cotización enviada)
• sale → Sales Order (pedido confirmado)
• cancel → Cancelled (cancelado)

Equipo de ventas por defecto: crm.team «Ventas».

Flujo típico: oportunidad CRM opcional → cotización sale.order → confirmación a pedido (sale) → entrega (stock.picking) → factura account.move (out_invoice).

Para lectura API en fase Ghost: sale.order, sale.order.line, crm.lead, crm.stage según Apéndice A EA.""",
    ),
    (
        5,
        "ans_20",
        "Where commissions and the commission matrix live in Odoo, if at all (app, custom fields or outside Odoo)",
        "Comisiones y matriz de comisiones",
        """App estándar Odoo «Commissions» (sale_commission): NO instalada. No existe matriz de comisiones de vendedores en modelos estándar ni tabla dedicada en custom para % por producto/vendedor.

Comisiones registradas en Odoo (ámbito distinto — medios de pago):
• Módulo gn_payment_extra en account.payment
• Campos: commission_percentage, commission_amount, commission_vat_amount (IVA 13% sobre comisión)
• Origen: convenios de tarjeta/POS (card_agreement_id, payment_method_type)

Comisiones bancarias en importación de extractos: módulos gn_banks_* (ej. cuenta 7010101.02 Comisiones Cobro POS).

Comisiones comerciales a vendedores (matriz NOUVA/Gestión):
• No localizadas en ERP al momento de este documento
• Si existen, probablemente fuera de Odoo (hojas de cálculo) o por confirmar con Contabilidad

Para agente CFO/Sales EA: no leer comisiones de ventas desde Odoo salvo que se implemente en el futuro; sí pueden leer pagos POS si se amplía alcance.""",
    ),
    (
        6,
        "ans_21",
        "How international purchase orders and import tracking are recorded "
        "(supplier, currency, due dates)",
        "OC internacionales y seguimiento de importación",
        """Compras internacionales — purchase.order:
• Proveedor: partner_id (res.partner proveedor)
• Moneda: currency_id (USD/EUR habitual en importaciones)
• Plazos: payment_term_id en la OC
• Flag custom: gn_labhospy_compra_internacional (boolean en formulario OC). Al facturar, propaga is_of_import=True en la factura de proveedor (_prepare_invoice). En datos actuales ninguna OC tiene el flag en True; las importaciones se marcan principalmente en factura.

Factura proveedor / importación — account.move (in_invoice):
• is_of_import (l10n_hn_account): factura tratada como importación (relajación validaciones SAR/CAI)
• gn_labhospy_es_importacion: campo adicional Labhospy en facturas
• Registros con is_of_import=True en BD: 62 facturas (histórico)

Recepciones y control aduanero:
• stock.picking ligado a purchase_id; si gn_labhospy_compra_internacional, validaciones en recepción (resolución SC para productos controlados — gn_labhospy)

Costos en destino:
• Módulo gn_import_landed_cost para prorrateo de gastos de importación a valoración de stock

Anticipos importación:
• Diario BNK26 «ANTICIPO A PROVEEDORES INTERNACIONALES» → cuenta 1010204.02

Seguimiento operativo de embarque/número de despacho: no hay modelo dedicado tipo «import.shipment»; usar referencia en PO (partner_ref, origin), factura y landed costs. Confirmar con Compras si usan campos en notas o documentos adjuntos (ir.attachment).""",
    ),
    (
        7,
        "—",
        "3.1 Sign-off: data map technically reviewed and confirmed",
        "3.1 Revisión mapa de datos",
        """Pendiente sesión conjunta Elite Architects + Nauiik: revisar el mapa escrito de cada campo que leen los agentes (Apéndice A) y confirmar técnicamente modelos, dominios y campos custom listados en secciones 2.1 y 3.

Responsable: equipo soporte Odoo (Nauiik).""",
    ),
    (
        8,
        "—",
        "3.1 Connection stable 7 days (user, API key, rules unchanged)",
        "3.1 Estabilidad conexión 7 días",
        """Pendiente hasta crear usuario «AI Agents – Elite Architects», grupo read-only, API key y mantener reglas sin cambios durante 7 días corridos sin huecos de sincronización.

Responsable: equipo soporte Odoo (Nauiik).""",
    ),
    (
        9,
        "—",
        "3.1 Test approval and rollback path for draft quotes before Sales go-live",
        "3.1 Prueba aprobación / rollback cotizaciones",
        """Pendiente fase posterior a Ghost: cuando se active grupo «AI Agents – Sales Drafts», planificar prueba end-to-end del flujo de aprobación humana y rollback de cotizaciones en borrador (sale.order state=draft only).

Responsable: equipo soporte Odoo + usuarios comerciales Labhospy.""",
    ),
]


def _add_questionnaire_sheet(wb, title, rows):
    ws = wb.create_sheet(title)
    headers = ["#", "Campo PDF", "Pregunta (documento EA)", "Pregunta (ES)", "Respuesta completa"]
    ws.append(headers)
    _style_header(ws)
    for row in rows:
        ws.append(row)
    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 42
    ws.column_dimensions["D"].width = 28
    ws.column_dimensions["E"].width = 90
    for r in range(2, ws.max_row + 1):
        for col in "ABCDE":
            ws[f"{col}{r}"].alignment = Alignment(wrap_text=True, vertical="top")
    return ws


def _style_header(ws, row=1):
    for cell in ws[row]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(wrap_text=True, vertical="top")


def main():
    wb = Workbook()

    ws = wb.active
    ws.title = "2.1 Cuestionario Odoo"
    headers = ["#", "Campo PDF", "Pregunta (documento EA)", "Pregunta (ES)", "Respuesta completa"]
    ws.append(headers)
    _style_header(ws)
    for row in SECTION_21:
        ws.append(row)
    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 42
    ws.column_dimensions["D"].width = 28
    ws.column_dimensions["E"].width = 90
    for r in range(2, ws.max_row + 1):
        for col in "ABCDE":
            ws[f"{col}{r}"].alignment = Alignment(wrap_text=True, vertical="top")

    _add_questionnaire_sheet(wb, "3. History y baseline", SECTION_3)

    SECTION_1 = [
        ("1", "ans_1", "Account lead", "[COMPLETAR] Nombre · WhatsApp · email"),
        ("1", "ans_2", "Consultor funcional", "[COMPLETAR]"),
        ("1", "ans_3", "Líder técnico", "[COMPLETAR]"),
        ("1", "ans_4", "Admin servidor/hosting", "[COMPLETAR] (infra gncs.io)"),
        ("1", "ans_5", "Escalamiento", "[COMPLETAR]"),
    ]

    ws_all = wb.create_sheet("Todas las secciones")
    ws_all.append(["Sección", "Campo PDF", "Ítem", "Respuesta"])
    _style_header(ws_all)
    for sec, field, item, ans in SECTION_1:
        ws_all.append((sec, field, item, ans))
    for row in SECTION_21:
        ws_all.append(("2.1", row[1], row[3], row[4]))
    for row in SECTION_3:
        ws_all.append(("3", row[1], row[3], row[4]))
    ws_all.column_dimensions["D"].width = 100
    for r in range(2, ws_all.max_row + 1):
        ws_all[f"D{r}"].alignment = Alignment(wrap_text=True, vertical="top")

    ws_bank = wb.create_sheet("Diarios_banco")
    ws_bank.append(["ID", "Código", "Nombre diario", "Cuenta contable"])
    _style_header(ws_bank)
    for j in JOURNALS:
        ws_bank.append(j)

    ws_sell = wb.create_sheet("Vendedores_OV")
    ws_sell.append(["Nombre", "Login Odoo", "Notas"])
    _style_header(ws_sell)
    sellers = [
        ("Leocadio Barahona Sanchez", "leob@labhospy.hn", "Alto volumen OV 2025+"),
        ("KARLA ELIZABETH GEORGE CANTILLANO", "karlag@labhospy.hn", "Alto volumen OV 2025+"),
        ("Marcela Garcia", "tiendatgu@labhospy.hn", ""),
        ("GABRIEL ANTONIO LOPEZ ELVIR", "oficial1tgu@labhospy.hn", ""),
        ("Milton Lizandro Canaca", "oficial2tgu@labhospy.hn", ""),
        ("Yuny Hugueth Miranda Martinez", "tiendasps01@labhospy.hn", "Validar con NOUVA"),
        ("ISAAC ANTONIO LAGOS FLORES", "tiendatgu02@labhospy.hn", "Validar con NOUVA"),
    ]
    for s in sellers:
        ws_sell.append(s)

    wb.save(OUT)
    print(f"Guardado: {OUT}")


if __name__ == "__main__":
    main()
