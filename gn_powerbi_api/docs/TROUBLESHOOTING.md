# Guía de Solución de Problemas - Power BI Connector

Esta guía te ayudará a resolver problemas comunes al configurar y usar el módulo Power BI Connector.

---

## Problema: "No se encontraron workspaces disponibles"

### Síntomas
- Al hacer clic en "Importar Workspaces" aparece el error: "No se encontraron workspaces disponibles"
- La prueba de conexión funciona pero muestra 0 workspaces

### Causas Posibles y Soluciones

#### 1. La aplicación no tiene acceso a ningún workspace

**Solución:**
1. Ve a [Power BI Service](https://app.powerbi.com)
2. Selecciona el workspace al que quieres dar acceso
3. Haz clic en **...** (menú) del workspace
4. Selecciona **Workspace access** (Acceso al workspace)
5. En **Add people or groups**, busca tu aplicación usando:
   - El **Object ID** de la aplicación (no el Client ID)
   - O el nombre de la aplicación
6. Selecciona el rol:
   - **Member** (Miembro): Permite ver y editar contenido
   - **Admin** (Administrador): Control total del workspace
7. Haz clic en **Add** (Agregar)

**Cómo encontrar el Object ID:**
- Ve a Azure Portal > Azure AD > App registrations
- Selecciona tu aplicación
- En Overview, copia el **Object ID** (no el Application ID)

---

#### 2. Las configuraciones de Admin API Settings no están habilitadas

**Solución:**
1. Ve a [Power BI Service](https://app.powerbi.com)
2. Haz clic en **⚙️ Configuración** > **Admin portal**
3. Ve a **Tenant settings** > **Admin API settings**
4. Habilita las siguientes configuraciones:

   **Si "Entire organization" está disponible:**
   - ✅ "Service principals can access read-only admin APIs" → Enabled for entire organization
   - ✅ "Service principals can access admin APIs used for updates" → Enabled for entire organization

   **Si solo puedes usar grupos específicos:**
   - Crea un grupo de seguridad en Azure AD (ver guía principal)
   - Agrega tu aplicación (Object ID) al grupo
   - Habilita las configuraciones para ese grupo específico

5. Haz clic en **Apply** después de cada cambio
6. **Espera 15 minutos** para que los cambios se propaguen

---

#### 3. Los permisos en Azure AD no están otorgados

**Solución:**
1. Ve a [Azure Portal](https://portal.azure.com) > Azure AD > App registrations
2. Selecciona tu aplicación
3. Ve a **API permissions**
4. Verifica que tengas estos permisos agregados:
   - ✅ **Tenant.Read.All** (Application permission)
   - ✅ **Tenant.ReadWrite.All** (Application permission)
5. Verifica que ambos tengan el estado **"Granted for [tu organización]"** con un ✅ verde
6. Si no están otorgados:
   - Haz clic en **Grant admin consent for [tu organización]**
   - Confirma haciendo clic en **Yes**

---

#### 4. El Client Secret ha expirado

**Solución:**
1. Ve a Azure Portal > Azure AD > App registrations > Tu aplicación
2. Ve a **Certificates & secrets**
3. Verifica la fecha de expiración del Client Secret
4. Si está expirado o cerca de expirar:
   - Haz clic en **+ New client secret**
   - Configura una descripción y fecha de expiración
   - Copia el **Value** inmediatamente (solo se muestra una vez)
   - Actualiza el Client Secret en Odoo

---

#### 5. Tiempo de propagación

**Solución:**
- Después de hacer cambios en Azure AD o Power BI Admin Portal, espera **15 minutos** antes de intentar nuevamente
- Los cambios pueden tardar en propagarse

---

## Problema: Error 401 (Unauthorized)

### Síntomas
- Error al obtener el token de acceso
- Mensaje: "Error de autenticación (401)"

### Causas y Soluciones

1. **Client Secret incorrecto o expirado**
   - Verifica que el Client Secret sea correcto
   - Verifica que no haya expirado

2. **Client ID incorrecto**
   - Verifica que el Client ID sea el Application (client) ID, no el Object ID

3. **Tenant ID incorrecto**
   - Verifica que el Tenant ID sea el Directory (tenant) ID correcto

---

## Problema: Error 403 (Forbidden)

### Síntomas
- Error al listar workspaces o crear datasets
- Mensaje: "Error de permisos (403)"

### Causas y Soluciones

1. **Permisos no otorgados en Azure AD**
   - Verifica que Tenant.Read.All y Tenant.ReadWrite.All tengan consentimiento del administrador

2. **Admin API Settings no habilitadas**
   - Habilita las configuraciones en Power BI Admin Portal (ver sección 2 arriba)

3. **La aplicación no tiene acceso al workspace**
   - Agrega la aplicación al workspace (ver sección 1 arriba)

---

## Problema: La aplicación no aparece al buscar en "Workspace access"

### Solución

Power BI busca por **Object ID**, no por Client ID:

1. Ve a Azure Portal > Azure AD > App registrations > Tu aplicación
2. En **Overview**, copia el **Object ID** (no el Application ID)
3. En Power BI, busca usando el **Object ID**
4. Si aún no aparece, intenta buscar por el nombre de la aplicación

---

## Verificación Rápida - Checklist

Usa este checklist para verificar que todo esté configurado correctamente:

### Azure AD
- [ ] La aplicación está registrada en Azure AD
- [ ] Tienes un Client Secret válido (no expirado)
- [ ] Los permisos Tenant.Read.All y Tenant.ReadWrite.All están agregados
- [ ] El consentimiento del administrador está otorgado (✅ verde)
- [ ] Si usas grupos específicos: la aplicación está en el grupo de seguridad

### Power BI Admin Portal
- [ ] "Service principals can access read-only admin APIs" está habilitada
- [ ] "Service principals can access admin APIs used for updates" está habilitada
- [ ] Si usas grupos específicos: el grupo está seleccionado en las configuraciones

### Power BI Workspaces
- [ ] La aplicación (Object ID) está agregada a al menos un workspace
- [ ] La aplicación tiene rol Member o Admin en el workspace

### Odoo
- [ ] Tenant ID está correcto
- [ ] Client ID está correcto
- [ ] Client Secret está correcto y no ha expirado
- [ ] La prueba de conexión funciona
- [ ] Esperaste 15 minutos después de hacer cambios

---

## Obtener Ayuda Adicional

Si después de seguir todos los pasos el problema persiste:

1. **Revisa los logs de Odoo** para ver errores detallados:
   ```bash
   tail -f /var/log/odoo/odoo.log | grep powerbi
   ```

2. **Verifica los logs en Azure AD**:
   - Azure Portal > Azure AD > Sign-in logs
   - Filtra por tu aplicación

3. **Verifica los logs en Power BI**:
   - Power BI Admin Portal > Audit logs

4. **Información útil para reportar el problema**:
   - Código de error HTTP (si hay)
   - Mensaje de error completo
   - Estado de la conexión en Odoo
   - Resultado de "Probar Conexión"
   - Última fecha de prueba exitosa

---

## Comandos Útiles para Diagnóstico

### Verificar token de acceso
En Odoo, ve a Power BI > Conexión y haz clic en "Probar Conexión". Esto verificará:
- Que el token se pueda obtener
- Que la API responda correctamente
- Cuántos workspaces están disponibles

### Verificar permisos en Azure AD
```bash
# Desde Azure Portal, verifica:
# 1. API permissions > Estado de los permisos
# 2. Certificates & secrets > Estado del Client Secret
```

### Verificar configuración en Power BI
```bash
# Desde Power BI Admin Portal, verifica:
# 1. Tenant settings > Admin API settings
# 2. Workspace > Workspace access > Miembros
```

