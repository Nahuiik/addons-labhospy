/** @odoo-module **/

import { patch } from '@web/core/utils/patch';
import { NavBar } from '@web/webclient/navbar/navbar';
import { onMounted, onWillStart, onPatched } from '@odoo/owl';
import { useService } from '@web/core/utils/hooks';

/**
 * Parche para mostrar el nombre personalizado del systray
 */
patch(NavBar.prototype, {
    setup() {
        super.setup();
        this.orm = useService('orm');
        this.ui = useService('ui');
        this.systrayName = null;
        this.companyName = null;
        
        onWillStart(async () => {
            await this._loadSystrayName();
        });
        
        onMounted(() => {
            this._updateSystrayName();
            // Ejecutar después de un pequeño delay para asegurar que el DOM esté listo
            setTimeout(() => this._updateSystrayName(), 100);
            setTimeout(() => this._updateSystrayName(), 500);
        });

        onPatched(() => {
            this._updateSystrayName();
        });
    },

    /**
     * Cargar el nombre del systray desde la empresa actual
     */
    async _loadSystrayName() {
        try {
            const companyId = this.ui.cpyId();
            if (companyId) {
                const company = await this.orm.read(
                    'res.company',
                    [companyId],
                    ['systray_name', 'name']
                );
                if (company && company.length > 0) {
                    this.companyName = company[0].name;
                    // Si hay un nombre personalizado, usarlo; si no, usar el nombre de la empresa
                    this.systrayName = company[0].systray_name || company[0].name;
                } else {
                    this.systrayName = null;
                    this.companyName = null;
                }
            }
        } catch (error) {
            console.warn('Error loading systray name:', error);
            this.systrayName = null;
            this.companyName = null;
        }
    },

    /**
     * Actualizar el nombre en el systray
     */
    _updateSystrayName() {
        if (!this.systrayName || !this.companyName) {
            return;
        }

        // Buscar el navbar principal
        const navbar = document.querySelector('.o_main_navbar') || document.querySelector('nav.o_main_navbar');
        if (!navbar) {
            return;
        }

        // Buscar elementos en el systray que puedan contener el nombre de la empresa
        const systray = navbar.querySelector('.o_menu_systray');
        if (!systray) {
            return;
        }

        // Evitar el menú de usuario y sus elementos hijos
        const userMenu = systray.querySelector('.o_user_menu');
        
        // Buscar elementos de texto en el systray, excluyendo el menú de usuario
        const textElements = systray.querySelectorAll('span, div, a, button, .dropdown-toggle');
        textElements.forEach(element => {
            // Saltar elementos dentro del menú de usuario
            if (userMenu && userMenu.contains(element)) {
                return;
            }
            
            // Saltar elementos que contengan iconos o imágenes
            if (element.querySelector('i, img, svg')) {
                return;
            }
            
            // Saltar elementos que sean botones o enlaces con iconos
            if (element.classList.contains('btn') && element.querySelector('i')) {
                return;
            }
            
            const text = (element.textContent || '').trim();
            
            // Solo reemplazar si el texto coincide exactamente con el nombre de la empresa
            // y no es hora, moneda, o ya tiene el nombre personalizado
            if (text === this.companyName || text === this.systrayName) {
                // Verificar que no sea hora o moneda
                if (!text.match(/^\$?\d+/) && !text.match(/^\d+:\d+\s*(a|p)\.m\./i)) {
                    // Verificar que no sea un elemento padre que ya fue actualizado
                    const parentText = (element.parentElement?.textContent || '').trim();
                    if (parentText !== this.systrayName) {
                        element.textContent = this.systrayName;
                        element.classList.add('o_gn_systray_brand');
                        element.style.removeProperty('color');
                        if (element.hasAttribute('title')) {
                            element.setAttribute('title', this.systrayName);
                        }
                        element.setAttribute('data-systray-updated', 'true');
                    } else if (!element.hasAttribute('data-systray-updated')) {
                        element.classList.add('o_gn_systray_brand');
                        element.style.removeProperty('color');
                        element.setAttribute('data-systray-updated', 'true');
                    }
                }
            }
        });

        // Usar MutationObserver para actualizar elementos dinámicos solo una vez
        if (!this.systrayObserver) {
            this.systrayObserver = new MutationObserver(() => {
                // Actualizar siempre que haya un nombre del systray
                if (this.systrayName) {
                    // Usar un pequeño delay para evitar múltiples actualizaciones
                    clearTimeout(this.updateTimeout);
                    this.updateTimeout = setTimeout(() => {
                        this._updateSystrayName();
                    }, 200);
                }
            });

            this.systrayObserver.observe(navbar, {
                childList: true,
                subtree: true,
                characterData: true,
            });
        }
    },
});

