# Manual de Usuario — Tablero Financiero

**Módulo:** `gn_financial_dashboard` · **Versión:** 19.0.18.0.0 · **Odoo:** 19 CE
**Autor:** Grupo Nahuiik · **Base de datos de referencia:** LABHOSPY

---

## 1. ¿Qué es el Tablero Financiero?

Es un panel visual e interactivo que lee directamente la **contabilidad de Odoo**
(`account.move.line`) y la transforma en indicadores (KPIs), gráficos, un **puntaje
de salud financiera explicable**, alertas, planeación presupuestal y vigilancia
multi-año.

No modifica datos contables: **solo lee y presenta**. Complementa a los reportes BI
(`bi_financial_reports_comm`) sin reemplazarlos.

Tecnología: OWL + Chart.js en el frontend y un modelo `AbstractModel` con RPC en el
backend (`gn.financial.dashboard`).

---

## 2. Acceso y permisos

- **Ruta de menú:** `Contabilidad → Reportes → Tablero financiero`.
- **Acción cliente:** `gn_financial_dashboard` (`action_gn_financial_dashboard`).

| Perfil | Grupo Odoo | Qué puede hacer |
|---|---|---|
| Consulta | `account.group_account_readonly` | Ver el tablero y todas las pestañas. |
| Gerente contable | `account.group_account_manager` | Además: **exportar** (PDF/Excel), **configurar** umbrales/tema, ver **detalle** (drill-down) y editar **presupuestos**. |

Las capacidades sensibles (exportar, configurar, ver detalle) se controlan por el
método `_capabilities()` y se activan solo para gerentes.

---

## 3. Fuentes de datos

Todo se calcula a partir de los **apuntes contables** (`account.move.line`),
filtrados por compañía, fechas, estado de asiento y diarios seleccionados. Los KPIs
se agrupan por **tipo de cuenta** (`account_type`):

| Concepto | Tipos de cuenta usados |
|---|---|
| Ingresos | `income`, `income_other` |
| Costo de ventas | `expense_direct_cost` |
| Gastos | `expense`, `expense_depreciation` |
| Efectivo / bancos / caja | `asset_cash`, `liability_credit_card` |
| Cuentas por cobrar | `asset_receivable` |
| Cuentas por pagar | `liability_payable` |
| Anticipos | `asset_prepayments` |

> La antigüedad de cartera (aging) reconstruye el saldo **a la fecha de corte**
> (ajustando conciliaciones parciales posteriores), usa `date_maturity` o `date`
> del apunte, y excluye asientos cancelados. El filtro **Tramo cartera** permite
> elegir períodos de 15, 30, 45 o 60 días.

---

## 4. Barra de filtros (parte superior)

| Filtro | Descripción |
|---|---|
| **Desde / Hasta** | Rango de fechas del período analizado. |
| **Asientos** | `Solo asentado` (posted) o `Todos (incl. borrador)`. |
| **Tramo cartera** | Tamaño de los tramos de antigüedad: 15, 30, 45 o 60 días (por defecto 30). |
| **Comparar** | `Período anterior`, `Mismo período año anterior` o `Sin comparación`. |
| **Diarios** | Selección múltiple de diarios (bancos, caja, ventas, compras, etc.). |
| **Sucursal** | (Si `gts_branch_management` está instalado) Selección múltiple de sucursales. Aplica a P&L, flujo, balance y aging. |
| **Centro de costos** | (Si `analytic` está instalado) Selección múltiple de cuentas analíticas, agrupadas por plan. Aplica a **P&L y derivados** (ingresos, costo, gastos, margen, utilidad, score, radar, diagnóstico, presupuesto). El balance y la cartera no se restringen por analítica (limitación honesta: el saldo residual no tiene dimensión analítica). |
| **Proyecto** | (Si `project` está instalado y los proyectos tienen cuenta analítica asociada) Selección múltiple de proyectos; internamente se resuelven a su cuenta analítica. |
| **Aplicar / Refrescar** | Recalcula con los filtros actuales. |
| **PDF / Excel** | Exporta el resumen ejecutivo (solo gerentes). |

El indicador **"Actualizado: fecha hora"** muestra el último cálculo.

> **Detección suave de módulos.** Los selectores de sucursal/centro de costos/proyecto **aparecen solo si el módulo correspondiente está instalado** y existe la información (por ejemplo, sucursales activas, cuentas analíticas, proyectos con cuenta analítica). Si faltan, el filtro simplemente no se muestra y el dashboard funciona igual que antes.

---

## 5. Pestañas del tablero

El tablero carga cada pestaña **bajo demanda** (lazy loading) para mantener la
velocidad. El orden es:

1. **Resumen** — KPIs principales, puntaje por categoría, velocímetro de riesgo y
   radar financiero. Vista de control general.
2. **Ejecutivo** — Resumen "de una ojeada": tarjeta de salud, narrativa automática,
   4 KPIs clave con variación, utilidad por año y "Atención prioritaria".
3. **Rentabilidad** — Evolución mensual de ingresos/gastos/utilidad, cascada de
   resultados y composición de gastos. Ranking de gastos.
4. **Liquidez** — Razón corriente, prueba ácida, capital de trabajo y balance.
5. **Flujo de caja** — Entradas, salidas y saldo acumulado de bancos/caja por mes.
6. **Cartera** — Antigüedad de cuentas por cobrar y por pagar por tramos de días.
7. **Planeación** — Presupuesto vs. real, pronóstico de fin de año, simulador
   *what-if* y línea de tiempo financiera.
8. **Vigilancia** — Comparación multi-año, benchmarking multi-compañía, calendario
   financiero y centro de alertas inteligentes.
9. **Diagnóstico** — Detalle del puntaje por categoría, recomendaciones priorizadas,
   centro de decisiones y revisión de calidad de datos.

---

## 6. Puntaje de salud financiera (motor explicable)

El puntaje global (0–100) es un promedio **ponderado** de 6 categorías. Cada
categoría parte de 100 y descuenta puntos por cada criterio incumplido.

| Categoría | Peso | Qué evalúa |
|---|---|---|
| Rentabilidad | 25% | Utilidad neta, margen neto, margen bruto, gasto/ingreso. |
| Liquidez | 18% | Razón corriente, prueba ácida, capital de trabajo. |
| Flujo de caja | 17% | Flujo del período y saldo bancario. |
| Cobranza | 15% | % cartera vencida y % cartera +120 días. |
| Endeudamiento | 15% | Pasivo/Activo y peso de cuentas por pagar. |
| Calidad de datos | 10% | Incidencias contables detectadas. |

**Niveles del puntaje global:**

| Rango | Nivel | Etiqueta |
|---|---|---|
| 80–100 | excellent | Excelente |
| 60–79 | good | Buena |
| 40–59 | warning | Atención |
| 0–39 | risk | Riesgo |

**Velocímetro de riesgo:** `0.55 × score global + 0.45 × min(liquidez, flujo, cobranza)`.
Castiga el resultado cuando una dimensión crítica está muy baja, aunque el global
sea aceptable. Estados: Muy bajo, Bajo, Moderado, Alto, Crítico.

**Radar financiero (8 ejes):** las 6 categorías + Capital de trabajo + Crecimiento
(este último derivado de la tendencia de ingresos, utilidad y flujo).

Botón **"¿Por qué este puntaje?"** abre el desglose detallado con los criterios que
suman o restan.

---

## 7. Glosario de KPIs

### 7.1 KPIs base

| KPI | Cálculo | Interpretación |
|---|---|---|
| Ingresos | Suma de cuentas de ingreso | Volumen de operación. |
| Costo de ventas | Suma de costo directo | Se resta para la utilidad bruta. |
| Utilidad bruta | Ingresos − Costo de ventas | Eficiencia operativa. |
| Gastos | Gastos + depreciación | Una reducción suele ser favorable. |
| Utilidad neta | Utilidad bruta − Gastos | Positiva = rentabilidad. |
| Margen bruto | Utilidad bruta / Ingresos × 100 | Rentabilidad antes de gastos. |
| Margen neto | Utilidad neta / Ingresos × 100 | Rentabilidad final. |
| ROI | Utilidad neta / Activos × 100 | Eficiencia de los activos. |
| Flujo de caja | Entradas − salidas de efectivo | Positivo = genera efectivo. |
| Saldo bancario | Saldo de efectivo al corte | Disponibilidad. |
| Cuentas por cobrar | Saldo de clientes a la fecha | Vigilar cobranza. |
| Cuentas por pagar | Saldo con proveedores | Reducción favorable. |
| Capital de trabajo | Activo corriente − Pasivo corriente | Holgura de corto plazo. |
| Razón corriente | Activo corriente / Pasivo corriente | > 1 = solvencia corto plazo. |
| Prueba ácida | (Efectivo + por cobrar + anticipos) / Pasivo corriente | Liquidez sin inventario. |

### 7.2 KPIs avanzados (V20 Fase 1)

| KPI | Cálculo | Interpretación |
|---|---|---|
| **EBIT** | Utilidad neta + Intereses + Impuestos | Utilidad operativa sin financiamiento ni fiscalidad. |
| **EBITDA** | EBIT + Depreciación y amortización | Generación de efectivo operativo. |
| **Margen operativo** | EBIT / Ingresos × 100 | Eficiencia operativa sobre ventas. |
| **Margen EBITDA** | EBITDA / Ingresos × 100 | Útil para comparar entre empresas con distinta deuda. |
| **ROA** | Utilidad neta / Activos promedio × 100 | Rentabilidad sobre el activo (mejor que ROI). |
| **ROE** | Utilidad neta / Patrimonio promedio × 100 | Retorno para los socios. |
| **Rotación de activos** | Ingresos / Activos promedio | Veces que el activo genera ingresos. |
| **Rotación de inventarios** | Costo de ventas / Inventario promedio | Requiere configurar cuentas de inventario. |
| **Rotación de CxC** | Ingresos / CxC promedio | Mayor rotación = mejor cobranza. |
| **Rotación de CxP** | (Costo + Gastos) / CxP promedio | Equilibrar con cobranza. |
| **Apalancamiento financiero** | Activos promedio / Patrimonio promedio | Dependencia de la deuda. |
| **Cobertura de intereses** | EBIT / Intereses | > 1 = se cubre el costo financiero. |
| **Gasto por intereses** | Suma de cuentas de intereses configuradas | Base para EBIT y cobertura. |
| **Impuesto sobre la renta** | Suma de cuentas de impuesto configuradas | Base para EBIT. |
| **Depreciación y amortización** | `expense_depreciation` + cuentas configuradas | Diferencia entre EBIT y EBITDA. |

> **Saldos promedio:** las rotaciones, ROA, ROE y apalancamiento usan
> **(saldo inicial + saldo final) / 2**. Si el saldo promedio resulta cero o
> negativo, el ratio se devuelve como `0` (no aplica), evitando valores
> matemáticamente válidos pero financieramente engañosos.

> **EBIT/EBITDA/cobertura/inventario** requieren mapear las cuentas
> correspondientes en `Configuración → Configuración del Tablero Financiero →
> pestaña "Cuentas (EBIT/EBITDA)"`. Si no se mapean, los KPIs derivados
> quedarán en 0 y los ratios que dependen de ellos también.

Cada tarjeta y gráfico tiene un ícono de ayuda (**InfoTip**) con su definición,
fórmula y cuentas usadas.

---

## 8. Drill-down (ver el detalle)

Los gerentes pueden hacer **clic** en:

- Tarjetas de KPI → abre el **detalle de cuentas** (árbol financiero agrupado por tipo).
- Barras de la evolución mensual, cascada y composición de gastos.
- Tramos de la cartera (aging) por cobrar y por pagar.
- Meses del flujo de caja.
- Cuentas o terceros en el **panel de variaciones** (Diagnóstico) → abre los
  apuntes del componente.

El detalle abre los apuntes (`account.move.line`) filtrados por el contexto del
clic, permitiendo auditar el origen de cada cifra.

**KPIs basados en cuentas configuradas** (intereses, impuestos, depreciación,
inventario): el drill-down (`drill_type='config_kpi'`) abre los apuntes de las
cuentas configuradas para ese indicador.

---

## 9. Planeación (presupuesto, pronóstico y simulador)

- **Presupuesto/metas:** modelo editable `gn.financial.dashboard.budget` con líneas
  mensuales por categoría (ingresos, costo, gastos). Se accede desde su propio menú
  (solo gerentes) y el botón **"Generar líneas"** crea los 12 meses.
- **Real vs. presupuesto:** progreso y desviación por categoría.
- **Pronóstico de fin de año:** proyección por **regresión lineal** sobre la
  tendencia observada.
- **Simulador *what-if*:** ajusta porcentajes (ingresos, costos, gastos) y observa el
  impacto en la utilidad sin afectar datos reales.
- **Línea de tiempo financiera:** cierres, metas y fechas de corte.

---

## 10. Vigilancia

- **Comparación multi-año:** ingresos, gastos y utilidad de los últimos años (el año
  en curso es parcial, hasta la fecha de corte).
- **Benchmarking multi-compañía:** compara KPIs clave entre compañías relacionadas.
- **Calendario financiero:** próximos cobros, pagos y cierres.
- **Centro de alertas:** consolida alertas del motor de score, calidad de datos,
  presupuesto, cartera y calendario, clasificadas por severidad (crítica, advertencia,
  informativa).

---

## 10b. Análisis de variaciones (Diagnóstico)

Disponible en la pestaña **Diagnóstico**. Para cada KPI con variación relevante
vs. el período comparativo (Ingresos, Costo de ventas, Gastos y Utilidad neta),
el panel descompone el delta por causa:

- **Top 5 cuentas** que más cambiaron, con monto y % del delta total que
  explican.
- **Top 3 terceros** (clientes/proveedores) que más cambiaron.
- **Narrativa corta** del estilo: *"Utilidad bajó L 80,000 (-12%). Cuenta con
  mayor impacto: Servicios profesionales (-L 32,000). Tercero con mayor
  impacto: Cliente X (-L 18,000)."*

Las filas son **clicables**: abren los apuntes contables filtrados por la
cuenta o tercero correspondiente.

La narrativa principal también alimenta el resumen ejecutivo en la pestaña
**Ejecutivo**.

> **Umbrales:** se reporta solo si el delta absoluto ≥ 100 unidades de la
> moneda y representa ≥ 1 % del mayor valor entre el período actual y el
> comparativo, para evitar ruido.
>
> **Limitación:** el desglose por tercero respeta los filtros de compañía,
> diarios y sucursal, pero **no** el filtro analítico (los terceros se
> obtienen directamente de `account.move.line`).

---

## 10c. Dimensiones de análisis (V20 Fase 1)

Los selectores de **Sucursal**, **Centro de costos** y **Proyecto** (cuando
están disponibles) propagan automáticamente a todas las pestañas mediante el
objeto `filters` que se envía a cada RPC.

| Dimensión | Fuente | Alcance del filtro |
|---|---|---|
| **Sucursal** | `branch_id` en `account.move.line` (módulo `gts_branch_management`) | Columna real en todos los apuntes: aplica a P&L, flujo de caja, balance y aging. Máximo rendimiento. |
| **Centro de costos** | `auto_account_id` en `account.analytic.line` (módulo `analytic`, CE) | **Solo P&L y derivados** (ingresos, costo, gastos, margen, utilidad, score, radar, diagnóstico, presupuesto). El balance y la cartera **no** se filtran (el saldo residual no tiene dimensión analítica). |
| **Proyecto** | `project.project.analytic_account_id` (módulo `project`) | Igual que Centro de costos: el proyecto se resuelve a su cuenta analítica y se fusiona con los centros seleccionados. |

**Ruta de cálculo analítico.** Cuando hay al menos una cuenta analítica
seleccionada, el P&L se recalcula desde `account.analytic.line` (vía
`_read_group`), reemplazando solo las cuentas de resultado. El balance y la
cartera siguen calculándose desde `account.move.line`. Esto es **honesto**:
muestra el P&L del centro/proyecto, pero no inventa una cartera analítica
inexistente.

---

## 11. Configuración (gerentes)

**Configuración por compañía** (`gn.financial.dashboard.config`), umbrales de alerta:

| Umbral | Valor por defecto |
|---|---|
| Margen neto mínimo (%) | 5.0 |
| % máx. cartera vencida | 30.0 |
| % máx. cartera +120 días | 15.0 |
| Razón corriente mínima | 1.0 |
| Capital de trabajo mínimo | 0.0 |
| Flujo de caja mínimo | 0.0 |
| % máx. gasto sobre ingresos | 70.0 |

También: color principal, modo compacto, mostrar moneda y **visibilidad/orden de
secciones**.

**Pestaña "Cuentas (EBIT/EBITDA)" (V20 Fase 1).** Aquí se mapean las cuentas
contables que el módulo no puede inferir solo del `account_type`:

| Campo | Para qué |
|---|---|
| **Cuentas de intereses** | Calcular EBIT, EBITDA y la cobertura de intereses. |
| **Cuentas de impuestos sobre la renta** | Calcular EBIT y EBITDA. |
| **Cuentas de depreciación/amortización** | (Opcional) Suma extra a `expense_depreciation` cuando hay cuentas que no usan ese tipo. |
| **Cuentas de inventario** | Calcular la rotación de inventarios (saldo inicial + final / 2). Si está vacío, la rotación no se calcula. |

Sin este mapeo, los KPIs que dependen de él quedarán en 0 (es decir, "no
aplica"), pero el resto del tablero sigue funcionando con normalidad.

**Preferencias por usuario** (`gn.financial.dashboard.user.pref`): cada usuario puede
personalizar la visibilidad y el orden de pestañas/secciones; sus preferencias se
superponen a la configuración de la compañía. Cada usuario solo ve y edita las suyas
(regla de registro). Menú: *"Mis preferencias del Tablero"*.

---

## 12. Exportaciones y narrativa IA

- **PDF / Excel:** generan el reporte ejecutivo con KPIs, salud y alertas (solo
  gerentes).
- **Narrativa automática:** la pestaña Ejecutivo muestra un resumen en lenguaje
  natural (etiqueta "Automático"). Es determinista (basado en reglas) y está
  preparado como **punto de extensión para IA**: el método `_ai_generate(context)`
  puede sobreescribirse en un módulo dependiente para llamar a un LLM usando el
  contexto financiero estructurado, manteniendo el mismo contrato de salida.

---

## 13. Uso en móvil

El tablero es **responsive**:

- **≤768px (tablet):** las pestañas se vuelven una barra deslizable horizontal y los
  filtros se apilan.
- **≤540px (móvil):** los bloques colapsan a una columna, los KPIs van en dos
  columnas, las tablas (benchmark/pronóstico) tienen scroll horizontal y el diálogo
  de detalle ocupa el ancho completo.

El contenido se desplaza con la rueda del ratón dentro del contenedor del tablero.

---

## 14. Preguntas frecuentes y solución de problemas

**No veo la pestaña Ejecutivo / un cambio reciente.**
Refresca con recarga forzada (Ctrl+F5). Si persiste, el servidor pudo no recargar el
código: actualiza el módulo y reinícialo.

**No puedo exportar ni ver el detalle.**
Esas acciones requieren el grupo *Gerente contable* (`account.group_account_manager`).

**Las cifras no cuadran con un reporte BI.**
Verifica que coincidan los filtros: rango de fechas, estado de asiento (posted vs.
todos) y diarios seleccionados.

**El saldo bancario sale negativo.**
Es un dato real al corte; revisa conciliaciones o sobregiros. El motor genera una
alerta y una recomendación al respecto.

**No veo los selectores de Sucursal / Centro de costos / Proyecto.**
Esos selectores aparecen solo si el módulo correspondiente (`gts_branch_management`,
`analytic`, `project`) está instalado y hay datos disponibles. Si lo instalas
después, refresca el navegador (Ctrl+F5) para que aparezcan.

**Cambié los filtros de Centro de costos pero el aging y el saldo bancario no
cambian.**
Es intencional: la analítica solo aplica a P&L. El saldo residual (cartera) y
los saldos de balance no tienen dimensión analítica, así que se calculan
siempre a nivel compañía + sucursal. Esta limitación está documentada y se
mantiene para no inventar cifras.

**EBIT/EBITDA salen en 0.**
Falta mapear las cuentas de intereses e impuestos en *Configuración del
Tablero Financiero → pestaña "Cuentas (EBIT/EBITDA)"*. Mientras estén vacías,
EBIT = Utilidad neta y EBITDA = Utilidad neta + Depreciación.

**La rotación de inventarios sale en 0.**
Falta mapear las cuentas de inventario en la misma pestaña de configuración.
Si no existen como tales, no se puede calcular el inventario promedio.

**El panel de variaciones no muestra nada.**
Tres causas posibles: (1) no hay comparación seleccionada (elige *Período
anterior* o *Mismo período año anterior*); (2) los deltas son demasiado
pequeños para ser relevantes (< 100 monedas o < 1 %); (3) las cuentas del
KPI cambiaron de forma compensada (no hay un componente dominante).

---

## 14b. Plataforma no-code (V20 Fase 2)

A partir de la versión 19.0.14.0.0 el tablero incorpora un **constructor
de KPIs sin código**, **espacios de trabajo** (workspaces) y **objetivos
estratégicos**. Estas tres piezas conviven con todos los indicadores
nativos y se evalúan automáticamente cada vez que aplicas los filtros del
tablero (compañía, fechas, diarios, sucursal, centro de costos y proyecto).

### 14b.1 Constructor de KPIs personalizados

Permite a un gestor contable definir indicadores propios sin programar.
Disponible en **Contabilidad → Configuración → Tablero financiero
→ KPIs personalizados**.

Tipos de fórmula soportados:

1. **Balance de cuentas** — suma directa de una o varias cuentas
   contables (por ejemplo: solo cuentas 5XX del catálogo).
2. **Suma por tipo de cuenta** — agrega por uno o varios `account_type`
   (por ejemplo: `income,income_other`).
3. **Razón (numerador / denominador)** — cada lado se calcula con uno de
   los tipos anteriores. Marca *Multiplicar por 100* para porcentajes
   (margen, % de mora, etc.).
4. **Expresión** — aritmética simple sobre KPIs nativos
   (`revenue`, `cogs`, `gross_profit`, `expenses`, `net_profit`, `ebit`,
   `ebitda`, `total_assets`, `equity`, `receivables`, `payables`,
   `current_ratio`, etc.) y sobre los códigos de otros KPIs personalizados.
   Operadores permitidos: `+`, `-`, `*`, `/` y paréntesis. Cualquier otro
   token (funciones, atributos, importaciones) es rechazado por seguridad.

Parámetros adicionales:

- **Periodo:** *Movimientos del rango* (P&L) o *Saldo acumulado al corte*
  (balance).
- **Signo:** *Natural* (debito − credito), *Solo débito*, *Solo crédito* o
  *Invertido*. Para cuentas de ingreso usa **Invertido** para que el
  resultado quede positivo.
- **Formato:** monto, porcentaje, ratio, días o número.
- **Mostrar en Resumen:** añade el KPI como tarjeta destacada en la
  pestaña Resumen (opcional).
- **Mostrar en "Mis KPIs":** controla si aparece en la pestaña
  *Mis KPIs* (activo por defecto).
- **Meta / Umbral de alerta:** la tarjeta cambia a verde si la meta se
  alcanza y a ámbar si el umbral se rompe (según la dirección deseada:
  mayor es mejor / menor es mejor / neutro).

**Drill-down.** Cuando el KPI usa cuentas (tipos 1–3), un clic en la
tarjeta abre los apuntes contables que lo componen, respetando los
filtros activos. Los KPIs de expresión no soportan drill-down porque no
representan un conjunto único de cuentas.

**Buenas prácticas.** Usa el código (campo `code`) como un identificador
estable y único — es la variable que otros KPIs pueden referenciar en una
expresión. El botón **Previsualizar** en el formulario evalúa el KPI con
los filtros por defecto y muestra una notificación con el resultado.

### 14b.2 Pestaña "Mis KPIs"

Una pestaña dedicada que muestra todos los KPIs marcados como *Mostrar
en "Mis KPIs"* y el panel de **Objetivos estratégicos**. Los gestores
contables ven los botones **Crear / Editar KPI** y **Configurar
objetivos** para acceder rápidamente al backoffice.

### 14b.3 Objetivos estratégicos

En **Contabilidad → Configuración → Tablero financiero → Objetivos
estratégicos** se definen metas medibles sobre cualquier KPI:

- **Fuente:** KPI del sistema (revenue, ROA, ROE, EBITDA, etc.) o un
  KPI personalizado.
- **Dirección:** *Alcanzar o superar la meta* (mayor=mejor) o
  *Mantenerse por debajo de la meta* (menor=mejor).
- **Meta** numérica y **fecha límite** (opcional).
- **Responsable** y **peso** (para ordenar los objetivos en la UI).

En el tablero el panel de objetivos muestra una barra de progreso, el
valor actual, la meta formateada y un semáforo:

- **Verde (Alcanzado):** la meta se cumplió.
- **Azul (En curso):** progreso parcial.
- **Rojo (Vencido):** la fecha límite pasó y no se alcanzó la meta.

Un clic abre el objetivo en su formulario para editar nota, plazo o meta.

### 14b.4 Espacios de trabajo (workspaces)

Permite guardar layouts personalizados del tablero. En la barra de
filtros aparece un selector de **Espacio** con los workspaces propios y
los compartidos por otros usuarios de la misma compañía (en modo solo
lectura).

El botón engranaje abre un cuadro de diálogo para:

- **Guardar como…** crear un nuevo workspace con el orden actual de
  pestañas y secciones.
- **Predeterminado** marcar uno como el workspace que se carga al abrir
  el tablero.
- **Compartir** publicar el workspace para que otros usuarios de la
  empresa puedan elegirlo como preset.
- **Duplicar / Eliminar** sobre el workspace activo.

Cada usuario tiene un workspace por defecto que se crea automáticamente
la primera vez que abre el tablero. Solo el propietario puede editar o
borrar un workspace; los compartidos son consumibles pero no editables.

### 14b.5 Performance

- La pestaña *Mis KPIs* carga bajo demanda; mientras no se abra, no se
  evalúan los KPIs personalizados.
- El evaluador comparte la matriz de sumarios contables (`_per_account_sums`)
  entre todos los KPIs personalizados de la misma compañía: una sola
  consulta por compañía/periodo aunque tengas decenas de KPIs.
- Las expresiones se evalúan con un parser AST restringido — no se usa
  `eval()` ni se acepta acceso a atributos, llamadas a funciones o
  importaciones.

### 14b.6 Permisos

- **Gestor contable** crea, edita y elimina KPIs personalizados y
  objetivos.
- **Contador / consultor** los visualiza en el tablero pero no puede
  modificarlos.
- **Cualquier usuario** gestiona sus propios workspaces; los workspaces
  compartidos requieren permisos de gestor contable para crearse pero
  son visibles para toda la empresa.

---

## 14c. Inteligencia de entidades (V20 Fase 3)

A partir de la versión 19.0.15.0.0 el tablero incluye una pestaña
**Inteligencia** con tres sub-pestañas: Productos, Clientes y Proveedores.
Cada una calcula rankings, scores y recomendaciones sobre los apuntes
contables del periodo activo y respeta todos los filtros del tablero
(compañía, fechas, diarios, sucursal, analítica, proyecto).

### 14c.1 Productos (Top, ABC y pérdidas)

La fuente de datos es `account.move.line` filtrada por las cuentas de
tipo `income`/`income_other` para los **ingresos** y por
`expense_direct_cost` para el **costo**. Por cada `product_id` se calcula:

- **Ingresos, costo y margen** (importe absoluto y porcentaje).
- **Cantidad** vendida (campo `quantity` del apunte).
- **Frecuencia** (número de facturas distintas en que aparece).
- **Participación %** del total de ingresos.

**Análisis ABC.** Los productos se ordenan por ingresos descendente y se
clasifican según el porcentaje acumulado:

- **A** (badge verde): primeros productos que suman el 80 % de los ingresos.
- **B** (badge ámbar): siguiente 15 %.
- **C** (badge gris): último 5 % (cola larga).

La tarjeta de resumen muestra cuántos productos pertenecen al grupo A
(la regla 80/20 te dice cuántos productos generan el 80 % del negocio).

**Productos en pérdida.** Si el margen calculado es negativo, el producto
aparece en una sección dedicada con su pérdida estimada (top 10 peores).
Esto suele indicar precios mal configurados, descuentos excesivos o
costos imputados de más.

**Drill-down.** Un clic en cualquier fila abre los apuntes contables de
ingreso del producto en el rango activo.

### 14c.2 Clientes (scoring 0-100)

Por cada cliente con movimiento en el periodo se calcula un **score
ponderado 0-100** con cinco subcomponentes (cada uno también 0-100):

| Componente | Peso | Interpretación |
|---|---|---|
| **Valor** | 30 | Ingresos del cliente vs. el top cliente del período. |
| **Frecuencia** | 15 | Nº de facturas vs. el cliente más frecuente. |
| **Pago** | 30 | DSO (días para cobrar): 100 si ≤30 d, 0 si ≥120 d, lineal. |
| **Mora** | 20 | % vencido sobre saldo: 100 si 0 %, 0 si ≥40 %, lineal. |
| **Antigüedad** | 5 | Días desde la primera factura (100 a partir de 2 años). |

Los clientes se clasifican en cinco *tiers*:

- **Champion** (verde): score ≥ 80. Cliente estratégico ideal.
- **Good** (verde claro): 65 ≤ score < 80.
- **Average** (gris): 50 ≤ score < 65.
- **Risky** (ámbar): 35 ≤ score < 50.
- **Critical** (rojo): score < 35.

**Recomendaciones automáticas.** Cada cliente recibe sugerencias
contextualizadas: gestión de cobranza, renegociación de términos,
re-engagement para clientes de baja frecuencia o programas premium para
clientes leales sin mora.

**Concentración.** Las tarjetas superiores muestran el % de ingresos
representado por los top 5 y top 10 clientes (riesgo de dependencia).

**Alertas.** El panel rojo lista clientes top con score crítico (< 50) y
mora > 20 %: prioridad para el departamento de cobranza.

**Drill-down.** Clic en una fila abre los apuntes de ingreso del cliente
en el período activo.

### 14c.3 Proveedores (scoring 0-100)

Misma idea aplicada a proveedores. La fuente son cuentas de tipo
`expense`, `expense_direct_cost` y `expense_depreciation`.

| Componente | Peso | Interpretación |
|---|---|---|
| **Valor** | 25 | Compras vs. el top proveedor. |
| **Frecuencia** | 15 | Nº de facturas. |
| **Pago** | 25 | DPO ideal 30-60 d. <15 d (pagamos demasiado rápido) o >120 d (atraso) penalizan. |
| **Concentración** | 25 | A menor dependencia, mayor score. |
| **Antigüedad** | 10 | Relación histórica. |

**Riesgo de dependencia.** Cualquier proveedor que concentre ≥ 25 % de
las compras aparece como alerta en el panel ámbar; conviene diversificar
o negociar acuerdos preferenciales.

**Recomendaciones automáticas.** Reducir dependencia, negociar plazos
más largos cuando pagamos muy rápido o atender saldos vencidos.

### 14c.4 Performance

- Carga **bajo demanda** (lazy) por sub-pestaña. Solo se evalúa la
  sub-pestaña activa.
- Usa `_read_group` para los agregados principales (ingresos/costos/
  cantidades/facturas) y un único `search_read` agregado para la
  exposición (CxC/CxP). En BDs grandes esto se mantiene en pocos
  segundos.
- Sin caché persistente: cada *Aplicar* recarga los datos del periodo,
  pero los filtros no recalculan las otras sub-pestañas hasta que se
  vuelvan a abrir.

### 14c.5 Permisos

- **Contador (group_account_readonly)** ve la pestaña Inteligencia,
  scores y recomendaciones.
- **Gestor contable (group_account_manager)** además puede hacer
  drill-down a los apuntes (clic en la fila).

---

## 14d. Dashboards por área (V20 Fase 4)

A partir de la versión 19.0.16.0.0 el tablero incluye una pestaña
**Áreas** con sub-pestañas que aparecen *solo si* el módulo de origen
está instalado. Esto permite al financiero ver, sin salir del tablero,
los KPIs operativos que más afectan la liquidez y la rentabilidad.

Las sub-pestañas estándar son: **Comercial** (`sale`/`sale_management`),
**Compras** (`purchase`) e **Inventario** (`stock`/`stock_account`). Si
ninguna de ellas está instalada, la pestaña Áreas se oculta por
completo.

### 14d.1 Comercial

Calcula sobre `sale.order` / `sale.order.line` del rango activo (por
`date_order`) y la compañía seleccionada. KPIs:

- **Ventas confirmadas** (estado `sale`): monto sin impuestos y nº de
  órdenes.
- **Pipeline** (estados `draft` y `sent`): valor potencial en cotizaciones.
- **Ticket promedio:** `confirmed_amount / confirmed_count`.
- **Conversión:** `confirmadas / (confirmadas + pipeline + canceladas)`.

Rankings (top 15):

- **Vendedores** (`user_id`), **equipos** (`team_id`), **clientes** y
  **productos vendidos** ordenados por monto.
- Gráfica mensual de ventas confirmadas.
- Botón "Ver órdenes" abre la lista de `sale.order` confirmadas con los
  mismos filtros.

### 14d.2 Compras

Calcula sobre `purchase.order` / `purchase.order.line`. KPIs:

- **Compras confirmadas** (estado `purchase`): monto y conteo.
- **RFQ / borradores** (`draft`, `sent`, `to approve`).
- **Lead time promedio** en días: `effective_date - date_order` sobre
  las POs con recepción registrada.
- **On-time %:** porcentaje de POs entregadas antes o el mismo día que
  `date_planned`.

Rankings (top 15): **proveedores**, **compradores** y **productos
comprados**. Gráfica mensual y acceso directo a la lista de POs.

### 14d.3 Inventario

Usa `stock.quant` filtrado por ubicaciones internas de la compañía
activa. KPIs:

- **Valor total del stock:** suma del campo `value` de los quants (si
  `stock_account` está instalado; si no, se calcula con `standard_price`).
- **SKUs en stock:** nº de productos con cantidad > 0.
- **Sin movimiento N días:** productos con stock > 0 que no han tenido
  `stock.move` en estado `done` durante los últimos N días (90 por
  defecto, configurable en la llamada RPC vía `no_move_days`).
- **Movimientos del periodo:** conteo de entradas (`+`) y salidas (`-`)
  done durante el rango activo.

Rankings: **top productos por valor** y **stock parado** (slow movers
ordenados por valor congelado descendente — los más prioritarios para
liberar caja). Un clic en cualquier fila abre la ficha del producto.

### 14d.4 Hook de extensión (Hospitalario y otros)

Para añadir un panel de área propio (p.ej. *Hospitalario*,
*Manufactura*, *Servicios*) sin tocar el módulo principal, crea un
módulo descendente que herede `gn.financial.dashboard` y sobreescriba el
método `_register_area_panels()`:

```python
from odoo import _, api, models

class HospitalDashboard(models.AbstractModel):
    _inherit = 'gn.financial.dashboard'

    def _register_area_panels(self):
        panels = super()._register_area_panels()
        panels.append({
            'key': 'hospital',
            'label': _('Hospitalario'),
            'icon': 'fa-medkit',
            'rpc': 'get_hospital_area_data',
        })
        return panels

    @api.model
    def get_hospital_area_data(self, filters):
        # Calcula tus KPIs operativos (pacientes, exámenes,
        # ocupación, etc.) y devuélvelos en un payload propio.
        return {'available': True, 'kpis': {...}, ...}
```

Una vez instalado el módulo, la sub-pestaña aparecerá automáticamente
en **Áreas → Hospitalario**. El frontend renderiza por defecto el JSON
del payload; para una vista enriquecida puedes registrar tu propio
componente OWL y extender el template con `xpath`.

### 14d.5 Performance

- Cada sub-pestaña carga **bajo demanda** (lazy). Cambiar el filtro
  obliga a recalcular solo la sub-pestaña activa.
- Los rankings (vendedores, productos, etc.) usan `_read_group` con
  `limit=15` y orden directo desde PostgreSQL.
- `get_inventory_data` filtra `quantity > 0` para evitar productos
  residuales y luego reordena localmente por valor (incluye fallback a
  `standard_price` cuando `stock_account` no costeó la línea).

### 14d.6 Permisos

- **Contador / consultor** (`account.group_account_readonly`) ve la
  pestaña Áreas y sus rankings.
- **Gestor contable** (`account.group_account_manager`) además puede
  hacer drill-down a las listas operativas (sale.order, purchase.order,
  product.product).
- El acceso a los modelos operativos (`sale.order`, `purchase.order`,
  `stock.quant`) se realiza con `sudo()`: el dashboard agrega
  información pero respeta el filtro de compañía activo.

---

## 14e. Predicciones (V20 Fase 5)

A partir de la versión 19.0.17.0.0 el tablero incluye una pestaña
**Predicciones** que combina pronóstico, score de salud financiera,
simulación de escenarios "what-if" y comparativa contra un benchmark
sectorial. Está disponible para usuarios con acceso al tablero (no
requiere módulos adicionales).

### 14e.1 Pronóstico

Construye series mensuales históricas (12, 18, 24 o 36 meses) y
proyecta los próximos 3, 6, 9 o 12 meses para cinco KPIs clave:

- **Ingresos** (INCOME_TYPES)
- **Utilidad bruta** (Ingresos − COGS)
- **Gastos operativos** (EXPENSE_TYPES)
- **Utilidad neta** (Ingresos − COGS − Gastos)
- **Flujo de caja del mes** (entradas − salidas en cuentas de caja/banco)

El motor de pronóstico aplica suavizado de Holt (nivel + tendencia)
cuando hay ≥ 3 puntos, y mínimos cuadrados como fallback. Cada
proyección incluye una banda heurística de ±1σ (desviación estándar
residual del ajuste) para indicar incertidumbre.

> **Performance:** las series se calculan con un solo `_read_group` por
> compañía sobre `account.move.line`, agrupando por `date:month` y
> `account_id`. Los filtros analíticos se ignoran en esta pestaña
> (complican la agregación mes a mes); los demás filtros se aplican
> normalmente.

### 14e.2 Score predictivo

Score 0–100 multifactor de la salud financiera del negocio. Combina
11 componentes con pesos calibrados:

| Componente | Peso | Rango (low → target) | Dirección |
|---|---|---|---|
| Margen bruto | 1.0 | 10 → 35 % | mayor mejor |
| Margen operativo | 1.2 | 0 → 12 % | mayor mejor |
| Margen neto | 1.0 | −2 → 10 % | mayor mejor |
| Razón corriente | 1.2 | 0.9 → 1.8 | mayor mejor |
| Prueba ácida | 0.8 | 0.6 → 1.2 | mayor mejor |
| Deuda / Activos | 1.0 | 0.8 → 0.4 | menor mejor |
| Cobertura de intereses | 0.6 | 1.5 → 4.0 | mayor mejor |
| Rotación de activos | 0.6 | 0.3 → 1.0 | mayor mejor |
| Rotación de inventario | 0.6 | 2.0 → 6.0 | mayor mejor |
| DSO (días cartera) | 0.8 | 90 → 40 | menor mejor |
| Tendencia de ingresos (mes/mes) | 1.5 | −2 → +3 % | mayor mejor |
| Tendencia de flujo de caja | 1.0 | ±5 % del último mes | mayor mejor |

Cada componente se evalúa con una rampa lineal entre `low` y `target`
(0..100). Los componentes sin datos suficientes se ignoran y los pesos
se redistribuyen, evitando colapsar el score por información ausente.

Tiers:

- **80–100** → *Excelente salud financiera*
- **65–79** → *Salud financiera sólida*
- **50–64** → *Salud financiera aceptable*
- **35–49** → *Riesgo elevado*
- **0–34** → *Estado crítico, atención inmediata*

Cada tier viene acompañado de una narrativa automática que destaca
fortalezas, oportunidades de mejora, promedio mensual proyectado de
ingresos y alertas si el pronóstico muestra meses con flujo de caja
negativo.

### 14e.3 Simulación de escenarios (what-if)

Permite evaluar el impacto de decisiones operativas sobre los KPIs
actuales sin tocar la base de datos. Parámetros:

| Parámetro | Efecto sobre |
|---|---|
| `price_delta_pct` | Multiplica los ingresos por (1 + Δ%) |
| `volume_delta_pct` | Multiplica ingresos **y** COGS por (1 + Δ%) |
| `cost_delta_pct` | Multiplica COGS por (1 + Δ%) |
| `opex_delta_pct` | Multiplica gastos operativos por (1 + Δ%) |
| `dso_delta_days` | Ajusta cartera y caja según `ingreso_diario × Δdías` |
| `dpo_delta_days` | Ajusta proveedores y caja según `cogs_diario × Δdías` |
| `capex` | Sale de caja y de activos corrientes |

Salida (`deltas`): para cada KPI, valor `base`, `new`, delta absoluto y
porcentaje. La simulación es determinista y se ejecuta en milisegundos
(usa los KPIs ya calculados del periodo activo).

### 14e.4 Benchmark sectorial

Compara los KPIs de tu compañía con un sector de referencia. Los datos
demo incluyen 4 sectores predefinidos (`hospital`, `lab`,
`distribution`, `services`) y 20 valores de referencia (márgenes,
liquidez, rotación, DSO, DPO, palanca).

Cada comparación muestra:

- **Tu compañía** (valor actual del KPI)
- **Benchmark** (`target_value` del sector)
- **Brecha** (% de diferencia)
- **Estado** semaforizado:
  - ✓ *Cumple* — la métrica alcanza o supera el target (en la dirección preferida).
  - ⚠ *Por debajo* — está entre `min` y `target`.
  - ✗ *En riesgo* — está por debajo de `min` (o por encima de `max` para KPIs invertidos).

Los benchmarks se gestionan en **Contabilidad → Configuración →
Benchmarks sectoriales**. Puedes añadir tus propios sectores o ajustar
los valores demo según tu mercado. Cada registro es por compañía (con
fallback a "sin compañía" para reglas globales).

### 14e.5 Permisos

- **Contador / consultor** ve forecast, score y benchmark.
- **Gestor contable** puede editar los benchmarks en la configuración.
- La simulación no requiere permisos adicionales: solo lee KPIs y
  calcula en memoria.

---

## 15. Actualizar el módulo (administradores)

```bash
python3 /home/odoo/src/odoo/odoo-bin \
  --addons-path=/home/odoo/src/odoo/addons,/home/odoo/src/labhospy \
  --data-dir=/home/odoo/data/labhospy \
  -d LABHOSPY -u gn_financial_dashboard --stop-after-init
```

Tras modificar archivos del módulo, **incrementa la versión** en `__manifest__.py`,
actualiza el módulo y verifica que termine sin errores (exit code 0).

---

## 14f. Decisiones e IA (V20 Fase 6)

La versión `19.0.18.0.0` añade la pestaña **Decisiones**, que centraliza:

- el centro de decisiones priorizadas,
- el motor de alertas inteligentes,
- el asistente IA financiero.

Reemplaza el reflejo manual de "qué debo hacer hoy" por una experiencia
guiada, accionable y trazable.

### 14f.1 Centro de decisiones (#22)

Sub-tab por defecto. Muestra hasta 8 tarjetas con las **decisiones
recomendadas** ordenadas por prioridad. Cada tarjeta incluye:

- número de ranking (`#1`, `#2`...),
- nivel de **urgencia** (Urgente / Alta / Media / Baja) con borde de
  color (rojo / naranja / azul / gris),
- **categoría** (Liquidez, Rentabilidad, Capital de trabajo, Riesgo,
  Crecimiento),
- breve resumen con datos reales,
- **acción sugerida** en azul (qué hacer concretamente).

Las decisiones se construyen automáticamente a partir de:

1. todas las **alertas activas** del motor,
2. los **productos con margen negativo** (pérdidas) detectados por la
   Inteligencia de Productos,
3. los **clientes en riesgo** (mora alta + score bajo) detectados por
   la Inteligencia de Clientes,
4. señales virtuales (concentración alta de cartera, score predictivo
   bajo, flujo de caja proyectado en rojo, objetivos incumplidos).

Haz click en una tarjeta para hacer drill-down al detalle relevante
(ficha del cliente, ficha del producto, ficha del objetivo o la
pestaña de alertas correspondiente).

### 14f.2 Alertas inteligentes (#21)

Sub-tab "Alertas". Combina dos motores:

#### a) Reglas configurables

Se gestionan desde **Contabilidad → Configuración → Reglas de alerta**.
Cada regla define:

- **KPI** a monitorear (margen bruto, razón corriente, mora %, score
  predictivo, etc. — 19 KPIs disponibles),
- **operador** (`<`, `≤`, `>`, `≥`, `entre [min, max]`,
  `fuera de [min, max]`),
- **umbral** (y umbral máximo en el caso de operadores de rango),
- **severidad** (Informativa, Advertencia, Crítica),
- **categoría**,
- **prioridad para Decisiones** (0-100, suma a la urgencia),
- **mensaje** (con placeholders `{value}`, `{threshold}`,
  `{threshold_max}`, `{kpi_label}`, `{company}`),
- **acción sugerida**.

El módulo carga por defecto **10 reglas estándar** cubriendo liquidez
(razón corriente, prueba ácida, caja negativa), rentabilidad (margen
bruto/operativo/neto), capital de trabajo (DSO, mora), y riesgo
(deuda/activos, cobertura de intereses). Puedes desactivarlas, editar
los umbrales, o crear nuevas reglas sin tocar código.

#### b) Señales virtuales

Siempre evaluadas, independientes de las reglas configurables:

- **Score predictivo bajo** (<50: Advertencia, <35: Crítica),
- **Flujo de caja proyectado en rojo** (≥50% de meses con pronóstico
  negativo: Advertencia; 100% en rojo: Crítica),
- **Concentración alta de cliente top-1** (≥30%: Advertencia, ≥50%:
  Crítica),
- **Dependencia alta de proveedor top-1** (≥40%: Advertencia, ≥60%:
  Crítica),
- **Objetivos estratégicos en riesgo** (status `off_track` /
  `critical`).

#### c) Persistencia, dedupe y auditoría

El botón **Sincronizar** sincroniza las alertas vivas con la tabla
`gn.financial.dashboard.alert.event`:

- crea un nuevo evento (`open`) por cada alerta nueva no presente,
- **auto-resuelve** los eventos cuya condición ya no aplica,
- respeta eventos `ack` o `snoozed` previos (no los reabre ni cierra).

Solo puede haber **un evento abierto por (code, compañía)** en cada
momento (de-duplicación lógica gestionada por el motor).

Cada evento queda en el chatter del registro con trazabilidad de
quién lo reconoció, quién lo resolvió, fecha de cada transición y
notas.

#### d) Tabla del histórico

Debajo de las alertas vivas aparece el **histórico reciente** (últimos
50 eventos) con badges de severidad/estado y botones para:

- 👁️ **Reconocer** (`open` → `ack`),
- ✅ **Marcar resuelta** (`open` / `ack` → `resolved`).

También puedes ir al menú **Contabilidad → Configuración → Histórico
de alertas** para ver la lista completa con filtros, agrupaciones y
acceso al chatter de cada evento.

### 14f.3 Asistente IA financiero (#23)

Sub-tab "Asistente IA". Chat conversacional en español donde puedes
preguntar en lenguaje natural sobre los datos del tablero.

Funciona **100% offline** por defecto: un clasificador de intents
basado en keywords identifica el tema (alertas, pronóstico, score,
caja, rentabilidad, ventas, clientes, proveedores, productos,
benchmark, decisiones, resumen) y combina una plantilla narrativa con
los **datos reales** calculados por los RPCs nativos del módulo
(respeta el filtro del tablero: compañía, periodo, dimensiones, modo
de asientos, etc.).

Cada respuesta incluye:

- una etiqueta del intent detectado (en mayúsculas, color gris),
- el texto narrativo con números reales,
- bullets (•) para listas (fortalezas, debilidades, top entidades),
- formato moneda con el símbolo de la compañía.

#### Sugerencias rápidas

Antes del input verás 6 chips clicables con preguntas frecuentes:

- "¿Cómo está la salud del negocio?"
- "¿Cuánto tengo en caja?"
- "Mostrar alertas urgentes"
- "Pronóstico para los próximos meses"
- "¿Qué clientes son los más rentables?"
- "¿Qué debo hacer ahora?"

Botón **Limpiar** vacía el historial de la sesión actual.

#### Integración con LLM externo (opcional)

El método Python `_ai_call_llm(question, filters)` está pensado como
**hook**: si devuelve un dict con `{answer, intent?, data?}`, esa respuesta
reemplaza a la nativa. Actívelo con parámetros del sistema
(`gn_fd.ai_llm_enabled`, `gn_fd.ai_llm_url`, `gn_fd.ai_llm_api_key`) o
sobrescriba el método en un addon descendiente para integrar OpenAI, Claude,
Mistral, Ollama u otro proveedor.

```python
class MyCompanyLLMBridge(models.AbstractModel):
    _inherit = 'gn.financial.dashboard'

    @api.model
    def _ai_call_llm(self, question, filters):
        if not self.env.company.openai_api_key:
            return None
        ctx = self._ai_get_context(filters)
        # ...llama tu LLM aquí...
        return {'answer': llm_response, 'intent': 'llm'}
```

### 14f.4 Drill-down desde Decisiones e IA

Las tarjetas de decisión y las alertas exponen un drill-down
contextual:

- `partner_id` → mayor del partner filtrado a posted + no
  reconciliado;
- `product_id` → ficha del producto;
- `goal_id` → form del objetivo estratégico;
- alertas sin payload específico → navega al sub-tab "Alertas" del
  hub.

### 14f.5 Configuración recomendada

1. Revisa el menú **Contabilidad → Configuración → Reglas de alerta**
   y ajusta los umbrales por defecto al tamaño y sector de la
   compañía (especialmente DSO, mora, prueba ácida, deuda/activos).
2. Crea reglas específicas para KPIs personalizados o sectoriales
   (por ejemplo: alarma cuando el costo % por sucursal supere cierto
   límite).
3. Programa un cron que llame a `sync_alert_events(filters)` una vez
   por día para mantener el histórico al día sin depender de que un
   usuario abra el tablero.
4. Si conectas un LLM externo, considera limitar el rate y filtrar
   las preguntas sensibles antes del envío al proveedor.
