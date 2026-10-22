/** @odoo-module **/

(function() {
    'use strict';

    /**
     * Genera o recupera un device_id único para este dispositivo
     */
    function getDeviceId() {
        const STORAGE_KEY = 'monitor_device_id';
        
        // Intentar obtener de localStorage
        let deviceId = localStorage.getItem(STORAGE_KEY);
        
        if (!deviceId) {
            // Generar nuevo UUID simple
            deviceId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                const r = Math.random() * 16 | 0;
                const v = c === 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
            
            // Guardar en localStorage
            localStorage.setItem(STORAGE_KEY, deviceId);
        }
        
        return deviceId;
    }

    /**
     * Envía un heartbeat al servidor
     */
    async function sendHeartbeat() {
        try {
            const deviceId = getDeviceId();
            // Obtener user_id desde la sesión si está disponible
            let userId = null;
            if (typeof odoo !== 'undefined' && odoo.session && odoo.session.uid) {
                userId = odoo.session.uid;
            }
            
            const response = await fetch('/monitoring/heartbeat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    device_id: deviceId,
                    user_id: userId,
                }),
            });
            
            if (!response.ok) {
                console.warn('Heartbeat failed:', response.status);
                return;
            }
            
            const data = await response.json();
            if (data.success) {
                // Opcional: log en modo debug
                if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                    console.debug('Heartbeat sent:', deviceId);
                }
            }
        } catch (error) {
            // Silenciar errores de red (puede ser offline, etc.)
            console.debug('Heartbeat error (ignored):', error.message);
        }
    }

    /**
     * Inicializa el sistema de heartbeat
     */
    function initHeartbeat() {
        // Obtener intervalo desde configuración (default 60 segundos)
        const intervalSeconds = parseInt(
            document.body.getAttribute('data-monitor-interval') || '60'
        );
        
        // Enviar heartbeat inmediatamente
        sendHeartbeat();
        
        // Configurar intervalo periódico
        const intervalId = setInterval(() => {
            sendHeartbeat();
        }, intervalSeconds * 1000);
        
        // Enviar heartbeat cuando la página se vuelve visible
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                sendHeartbeat();
            }
        });
        
        // Enviar heartbeat antes de cerrar la página
        window.addEventListener('beforeunload', () => {
            // Usar sendBeacon para requests síncronos al cerrar
            const deviceId = getDeviceId();
            let userId = null;
            if (typeof odoo !== 'undefined' && odoo.session && odoo.session.uid) {
                userId = odoo.session.uid;
            }
            
            if (navigator.sendBeacon) {
                const blob = new Blob([JSON.stringify({
                    device_id: deviceId,
                    user_id: userId,
                })], {type: 'application/json'});
                navigator.sendBeacon('/monitoring/heartbeat', blob);
            } else {
                sendHeartbeat();
            }
        });
        
        return intervalId;
    }

    // Inicializar cuando el DOM esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initHeartbeat);
    } else {
        initHeartbeat();
    }

    // Exportar para uso manual si es necesario
    window.MonitorHeartbeat = {
        sendHeartbeat: sendHeartbeat,
        getDeviceId: getDeviceId,
        initHeartbeat: initHeartbeat,
    };

})();
