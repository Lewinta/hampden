// Copyright (c) 2021, ahmadragheb and contributors
// For license information, please see license.txt

frappe.ui.form.on('Item Association', {
    refresh: function(frm) {
        $('#body_div').append(`<style>.grid-row div[data-fieldname="dependent_percentage"]{width: 100px}
		                              .data-row div[data-fieldname="cutting_loss_"]{width: 110px}</style>`)

    },
    update_system: function(frm) {
        frappe.call({
            method: 'hampden.api.update_items_with_associations',
            args: {
                item_association: frm.doc.name
            },
            callback: function(r) {
                if (r && r.message) {
                    frappe.msgprint(__('Items Updates Done') + ' !')
                }
            }
        })
    }
});