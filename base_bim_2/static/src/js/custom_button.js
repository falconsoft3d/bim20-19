odoo.define('base_bim_2.custom_button', function (require) {
    "use strict";

    var core = require('web.core');
    var Widget = require('web.Widget');

    console.log("Custom button 01")

    var CustomButton = Widget.extend({
        // template: 'base_bim_2.view_form_bim_concepts'
        switchModeToReadonly: function () {
            this.model.root.switchMode("readonly");
        },
    });

    console.log("Custom button 02")

    core.action_registry.add('base_bim_2_custom_button', CustomButton);

    console.log("Custom button 03")

    return CustomButton;
});