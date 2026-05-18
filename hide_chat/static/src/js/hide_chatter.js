/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Función para aplicar/remover la clase hide-chatter
function applyChatterVisibility() {
    const hideChatter = localStorage.getItem('hide_chatter') === 'true';
    if (document.body) {
        if (hideChatter) {
            document.body.classList.add('hide-chatter');
        } else {
            document.body.classList.remove('hide-chatter');
        }
    }
}

// Componente del botón toggle
class ChatterToggleButton extends Component {
    setup() {
        this.notification = useService("notification");
        this.state = useState({
            hidden: localStorage.getItem('hide_chatter') === 'true'
        });
        
        // Aplicar al montar el componente
        onMounted(() => {
            applyChatterVisibility();
        });
    }

    toggleChatter() {
        this.state.hidden = !this.state.hidden;
        localStorage.setItem('hide_chatter', this.state.hidden.toString());
        applyChatterVisibility();
        
        this.notification.add(
            this.state.hidden ? 'Chatter ocultado' : 'Chatter visible',
            { type: 'info' }
        );
    }
}

ChatterToggleButton.template = "hide_chat.ChatterToggleButton";

// Registrar el componente en el systray
registry.category("systray").add("ChatterToggleButton", {
    Component: ChatterToggleButton,
}, { sequence: 1 });
