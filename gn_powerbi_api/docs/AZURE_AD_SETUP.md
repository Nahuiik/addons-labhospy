# Guía de Configuración de Permisos en Azure AD para Power BI

Esta guía te ayudará a configurar los permisos necesarios en Azure AD para que tu aplicación pueda acceder a los Workspaces de Power BI.

## Requisitos Previos

- Acceso de administrador a Azure Portal
- Una aplicación registrada en Azure AD (App Registration)
- Acceso a Power BI Service (portal.powerbi.com)

---

## Paso 1: Registrar la Aplicación en Azure AD

1. Inicia sesión en [Azure Portal](https://portal.azure.com)
2. Busca y selecciona **Azure Active Directory**
3. En el menú lateral, selecciona **App registrations** (Registros de aplicaciones)
4. Haz clic en **+ New registration** (+ Nueva inscripción)

### Configuración de la Aplicación

- **Name**: Ingresa un nombre descriptivo (ej: "Odoo Power BI Connector")
- **Supported account types**: Selecciona según tu necesidad:
  - **Single tenant**: Solo usuarios de tu organización
  - **Multi-tenant**: Usuarios de cualquier organización
- **Redirect URI**: Opcional para Client Credentials, pero puedes dejar un valor por defecto
  - Tipo: **Web**
  - URI: `https://localhost` (solo para cumplir el campo requerido)

5. Haz clic en **Register** (Registrar)

### Guardar los Valores Importantes

Después de crear la aplicación, guarda estos valores:
- **Application (client) ID**: Este es tu `Client ID`
- **Directory (tenant) ID**: Este es tu `Tenant ID`

---

## Paso 2: Crear un Client Secret

1. En la página de tu aplicación registrada, ve a **Certificates & secrets** (Certificados y secretos)
2. Haz clic en **+ New client secret** (+ Nuevo secreto de cliente)
3. Configura:
   - **Description**: Ej: "Odoo Power BI Secret"
   - **Expires**: Selecciona la duración (recomendado: 24 meses)
4. Haz clic en **Add** (Agregar)
5. **IMPORTANTE**: Copia el **Value** del secreto inmediatamente. Solo se muestra una vez.
   - Este es tu `Client Secret`

---

## Paso 3: Configurar Permisos de API de Power BI

### 3.1 Agregar Permisos de Power BI

1. En la página de tu aplicación, ve a **API permissions** (Permisos de API)
2. Haz clic en **+ Add a permission** (+ Agregar un permiso)
3. Selecciona **Power BI Service** (si no lo ves, busca "Power BI" en la barra de búsqueda)
4. Selecciona **Application permissions** (Permisos de aplicación)
   - ⚠️ **Importante**: Debes usar "Application permissions", NO "Delegated permissions", porque estamos usando Client Credentials

### 3.2 Seleccionar los Permisos Necesarios

En la sección de **Application permissions** (Permisos de aplicación), verás los permisos disponibles para Power BI Service.

#### Permisos Disponibles:

Los permisos que verás son de nivel tenant (más amplios):

- ✅ **Tenant.Read.All** - Ver todo el contenido del tenant
  - **Descripción**: "View all content in tenant"
  - **Incluye**: Leer workspaces, datasets, tablas, reportes, dashboards
  - **Necesario para**: Listar workspaces, leer información de datasets

- ✅ **Tenant.ReadWrite.All** - Leer y escribir todo el contenido del tenant
  - **Descripción**: "Read and write all content in tenant"
  - **Incluye**: Crear, leer, actualizar y eliminar workspaces, datasets, tablas, datos
  - **Necesario para**: Crear datasets, insertar datos, actualizar tablas, eliminar filas

#### Recomendación:

Para que el módulo funcione completamente, marca **ambos permisos**:
- ✅ **Tenant.Read.All** (para operaciones de lectura)
- ✅ **Tenant.ReadWrite.All** (para operaciones de escritura)

**Nota**: Estos permisos son más amplios que los permisos específicos (Workspace.Read.All, Dataset.ReadWrite.All, etc.) que podrías encontrar en documentación antigua. Microsoft ha consolidado los permisos en estos dos de nivel tenant, que cubren todas las funcionalidades necesarias.

5. Marca ambos permisos haciendo clic en las casillas de verificación
6. Haz clic en **Add permissions** (Agregar permisos)

### 3.3 Otorgar Consentimiento del Administrador

⚠️ **CRÍTICO**: Para que los permisos funcionen con Client Credentials, debes otorgar el consentimiento del administrador:

1. En la página de **API permissions**, verás que los permisos tienen un estado "Not granted"
2. Haz clic en el botón **Grant admin consent for [tu organización]** (Otorgar consentimiento del administrador)
3. Confirma haciendo clic en **Yes** (Sí)

**Resultado esperado**: Todos los permisos deberían mostrar un ✅ verde con el estado "Granted for [tu organización]"

---

## Paso 4: Configurar Permisos en Power BI Service

Los permisos de Azure AD no son suficientes. También necesitas dar acceso a la aplicación en Power BI:

### 4.1 Acceder a Power BI Admin Portal

1. Inicia sesión en [Power BI Service](https://app.powerbi.com)
2. Haz clic en el icono de **Configuración** (⚙️) en la esquina superior derecha
3. Selecciona **Admin portal** (Portal de administración)
   - ⚠️ Solo disponible si tienes permisos de administrador de Power BI

### 4.2 Habilitar el Service Principal en Admin API Settings

1. En el Admin Portal, ve a **Tenant settings** (Configuración del inquilino)
2. Busca la sección **Admin API settings** (Configuración de Admin API)
3. Verás las siguientes opciones relacionadas con Service Principals:

#### Configuraciones Necesarias:

**Para operaciones básicas (listar workspaces, crear datasets, insertar datos):**

- ✅ **Service principals can access read-only admin APIs** (Service principals pueden acceder a Admin APIs de solo lectura)
  - **Necesario para**: Listar workspaces, leer información de datasets

- ✅ **Service principals can access admin APIs used for updates** (Service principals pueden acceder a Admin APIs usadas para actualizaciones)
  - **Necesario para**: Crear datasets, insertar/actualizar datos, eliminar filas

#### Configuraciones Opcionales:

- ⚠️ **Enhance admin APIs responses with detailed metadata** (Mejorar respuestas de Admin APIs con metadatos detallados)
  - Solo necesario si necesitas información adicional en las respuestas
  - Puede dejarse deshabilitado para operaciones básicas

- ⚠️ **Enhance admin APIs responses with DAX and mashup expressions** (Mejorar respuestas con expresiones DAX y mashup)
  - Solo necesario si trabajas con DAX o Power Query avanzado
  - Puede dejarse deshabilitado para operaciones básicas

#### ⚠️ Importante: Si "Entire organization" está deshabilitado

Si la opción **"Enabled for the entire organization"** está deshabilitada (greyed out), significa que tu organización tiene políticas de seguridad que requieren usar grupos específicos. En este caso, necesitas:

**4.2.1 Crear un Grupo de Seguridad en Azure AD**

1. Ve a [Azure Portal](https://portal.azure.com) > **Azure Active Directory**
2. En el menú lateral, selecciona **Groups** (Grupos)
3. Haz clic en **+ New group** (+ Nuevo grupo)
4. Configura el grupo:
   - **Group type**: Selecciona **Security** (Seguridad)
   - **Group name**: Ej: "Power BI Service Principals" o "Odoo Power BI Connectors"
   - **Group description**: Descripción opcional
   - **Azure AD roles can be assigned to the group**: Puedes dejarlo deshabilitado
5. Haz clic en **Create** (Crear)
6. **Guarda el nombre del grupo** - lo necesitarás en el siguiente paso

**4.2.2 Agregar el Service Principal al Grupo**

1. En Azure AD, ve a **App registrations** (Registros de aplicaciones)
2. Busca y selecciona tu aplicación (la que creaste en el Paso 1)
3. En la página de Overview, copia el **Object ID** (no el Application ID)
   - ⚠️ **Importante**: Necesitas el Object ID, no el Client ID
4. Ve a **Groups** (Grupos) en Azure AD
5. Busca y selecciona el grupo que creaste en el paso anterior
6. En el menú lateral, selecciona **Members** (Miembros)
7. Haz clic en **+ Add members** (+ Agregar miembros)
8. En el campo de búsqueda, pega el **Object ID** de tu aplicación
   - Si no aparece, busca por el nombre de la aplicación
9. Selecciona tu aplicación y haz clic en **Select** (Seleccionar)
10. Verifica que la aplicación aparezca en la lista de miembros

**4.2.3 Habilitar las Configuraciones en Power BI Admin Portal**

Ahora que tienes el grupo creado y la aplicación agregada:

1. Regresa a **Power BI Admin Portal > Tenant settings > Admin API settings**
2. Para cada configuración que necesites habilitar:
   - Haz clic en **"Disabled for the entire organization"** o en el toggle
   - Selecciona **"Enabled for specific security groups"**
   - En el campo de búsqueda, busca y selecciona el grupo que creaste (ej: "Power BI Service Principals")
   - Haz clic en **Apply** (Aplicar)
3. Repite el proceso para todas las configuraciones necesarias:
   - ✅ "Service principals can access read-only admin APIs"
   - ✅ "Service principals can access admin APIs used for updates"

**Nota**: Aunque estas configuraciones mencionan "Admin APIs", también controlan el acceso de Service Principals a las APIs regulares de Power BI. Es necesario habilitarlas para que tu aplicación pueda funcionar.

**Tiempo de propagación**: Los cambios pueden tardar hasta 15 minutos en aplicarse. Si después de configurar todo no funciona inmediatamente, espera unos minutos y vuelve a intentar.

### 4.3 Agregar la Aplicación a los Workspaces

Para que la aplicación pueda acceder a workspaces específicos:

#### Opción A: Agregar como Miembro del Workspace

1. Ve al workspace en Power BI Service
2. Haz clic en **...** (menú) del workspace
3. Selecciona **Workspace access** (Acceso al workspace)
4. En **Add people or groups** (Agregar personas o grupos), busca tu aplicación por su **Client ID** o nombre
5. Selecciona el rol:
   - **Member** (Miembro): Puede ver y editar contenido
   - **Admin** (Administrador): Control total del workspace
   - **Contributor** (Colaborador): Puede agregar contenido pero no ver todo
6. Haz clic en **Add** (Agregar)

#### Opción B: Usar PowerShell (Avanzado)

Si tienes muchos workspaces, puedes usar PowerShell para agregar la aplicación:

```powershell
# Conectar a Power BI
Connect-PowerBIServiceAccount

# Obtener el Object ID de tu aplicación (no el Client ID)
$appObjectId = "tu-object-id-de-azure-ad"

# Agregar la aplicación a un workspace
Add-PowerBIWorkspaceUser -WorkspaceId "workspace-id" -UserPrincipalName $appObjectId -AccessRight Member
```

---

## Paso 5: Verificar la Configuración

### 5.1 Verificar en Azure AD

1. Ve a tu aplicación en Azure AD
2. Verifica que en **API permissions**:
   - Todos los permisos estén marcados como "Granted for [tu organización]"
   - No haya advertencias en amarillo

### 5.2 Probar la Conexión desde Odoo

1. En Odoo, ve a **Power BI > Conexión**
2. Crea una nueva conexión con:
   - **Tenant ID**: El Directory (tenant) ID de Azure AD
   - **Client ID**: El Application (client) ID
   - **Client Secret**: El valor del secret que creaste
3. Haz clic en **Probar Conexión**
4. Si todo está bien configurado, deberías ver: "Conexión exitosa. Se encontraron X workspace(s)."

---

## Solución de Problemas

### Error: "AADSTS70011: The provided value for the input parameter 'scope' is not valid"

**Causa**: El scope no está correctamente configurado.

**Solución**: Asegúrate de que el scope sea exactamente: `https://analysis.windows.net/powerbi/api/.default`

### Error: "403 Forbidden" al listar workspaces

**Causas posibles**:
1. No se otorgó el consentimiento del administrador en Azure AD
2. Las configuraciones de Admin API Settings no están habilitadas en Power BI Admin Portal
3. La aplicación no está en el grupo de seguridad correcto (si usas grupos específicos)
4. La aplicación no tiene acceso al workspace específico
5. Los cambios aún no se han propagado (puede tardar hasta 15 minutos)

**Soluciones**:
1. Verifica que los permisos correctos estén agregados en Azure AD (Paso 3.2):
   - ✅ Tenant.Read.All
   - ✅ Tenant.ReadWrite.All
2. Verifica que el consentimiento del administrador esté otorgado (Paso 3.3)
3. Si "Entire organization" está deshabilitado:
   - Crea un grupo de seguridad en Azure AD (Paso 4.2.1)
   - Agrega tu aplicación (Object ID) al grupo (Paso 4.2.2)
   - Habilita las configuraciones para ese grupo específico (Paso 4.2.3)
4. Si "Entire organization" está disponible, habilita las configuraciones directamente (Paso 4.2)
5. Verifica que las configuraciones estén habilitadas:
   - ✅ "Service principals can access read-only admin APIs" (para operaciones de lectura)
   - ✅ "Service principals can access admin APIs used for updates" (para operaciones de escritura)
6. Agrega la aplicación al workspace como miembro (Paso 4.3)
7. Espera 15 minutos después de hacer cambios y vuelve a intentar

### Error: "No se encontraron workspaces disponibles"

**Causas posibles**:
1. La aplicación no tiene acceso a ningún workspace
2. Los permisos no están correctamente configurados

**Soluciones**:
1. Agrega la aplicación a al menos un workspace (Paso 4.3)
2. Verifica que los permisos `Workspace.Read.All` estén otorgados (Paso 3.2)

### La aplicación no aparece al buscar en "Workspace access"

**Causa**: Power BI busca por Object ID, no por Client ID.

**Solución**:
1. En Azure AD, ve a tu aplicación
2. Ve a **Overview** (Información general)
3. Copia el **Object ID** (no el Application ID)
4. Usa este Object ID para buscar en Power BI

---

## Resumen de Valores Necesarios en Odoo

Después de completar todos los pasos, necesitarás estos valores en Odoo:

| Campo en Odoo | Valor de Azure AD | Dónde encontrarlo |
|---------------|-------------------|-------------------|
| **Tenant ID** | Directory (tenant) ID | Azure AD > App registrations > Tu app > Overview |
| **Client ID** | Application (client) ID | Azure AD > App registrations > Tu app > Overview |
| **Client Secret** | Value del Client Secret | Azure AD > App registrations > Tu app > Certificates & secrets |

---

## Referencias Adicionales

- [Documentación oficial de Power BI REST API](https://docs.microsoft.com/en-us/rest/api/power-bi/)
- [Autenticación con Service Principal en Power BI](https://docs.microsoft.com/en-us/power-bi/developer/embedded/embed-service-principal)
- [Permisos de Power BI](https://docs.microsoft.com/en-us/power-bi/admin/service-admin-administering-power-bi-in-your-organization)

---

## Notas Importantes

1. **Client Credentials vs Delegated**: Este módulo usa Client Credentials, que es autenticación de aplicación. No requiere un usuario interactivo.

2. **Admin API Settings**: Aunque estas configuraciones mencionan "Admin APIs", también controlan el acceso de Service Principals a las APIs regulares de Power BI. Es necesario habilitarlas para que tu aplicación pueda funcionar.
   - Si "Entire organization" está deshabilitado, necesitas crear un grupo de seguridad en Azure AD y agregar tu aplicación a ese grupo (ver Paso 4.2.1 y 4.2.2).

3. **Permisos de Workspace**: Aunque tengas permisos en Azure AD y Admin API Settings habilitadas, también necesitas agregar la aplicación a cada workspace individual en Power BI.

4. **Seguridad**: El Client Secret es sensible. Guárdalo de forma segura y no lo compartas. Si se compromete, revócalo inmediatamente y crea uno nuevo.

5. **Expiración del Secret**: Los Client Secrets expiran. Configura un recordatorio para renovarlo antes de que expire.

6. **Workspaces Disponibles**: Con Client Credentials, solo verás los workspaces a los que la aplicación tiene acceso explícito. No verás todos los workspaces de la organización automáticamente.

7. **Permisos en Azure AD**: Los permisos disponibles son de nivel tenant:
   - **Tenant.Read.All** - Para operaciones de lectura (listar workspaces, leer datasets)
   - **Tenant.ReadWrite.All** - Para operaciones de escritura (crear datasets, insertar datos)
   - Estos permisos reemplazan a los permisos específicos más antiguos (Workspace.Read.All, Dataset.ReadWrite.All, etc.)

8. **Configuraciones Mínimas Necesarias**: Para que el módulo funcione correctamente, necesitas:
   - En Azure AD: Tenant.Read.All y Tenant.ReadWrite.All con consentimiento del administrador
   - En Power BI Admin Portal: Habilitar "Service principals can access read-only admin APIs" y "Service principals can access admin APIs used for updates"

