// Copyright (c) 2021, ahmadragheb and contributors
// For license information, please see license.txt

frappe.ui.form.on('Tray Assignment', {
    setup: function(frm) {
        if (frm.doc.docstatus == 0)
            frm.set_value('date', frappe.datetime.now_datetime())
    },
    refres: function(frm) {
        frm.fields_dict['tray_steps'].grid.wrapper.find('.grid-remove-rows').hide();
        frm.fields_dict['tray_steps'].grid.wrapper.find('.grid-footer').hide();
        frm.fields_dict['tray_steps'].grid.wrapper.find('.grid-row-check').hide();
        frm.fields_dict['tray_steps'].grid.wrapper.find('.row-index').css({ 'width': '39px', 'display': 'flex', 'justify-content': 'center' });

        frm.fields_dict['batch_order'].grid.wrapper.find('.grid-footer').hide();
        frm.fields_dict['batch_order'].grid.wrapper.find('.grid-row-check').hide();
        frm.fields_dict['batch_order'].grid.wrapper.find('.row-index').css({ 'width': '39px', 'display': 'flex', 'justify-content': 'center' });

    },
    order_barcode: function(frm) {
        frappe.call({
            method: 'add_order',
            doc: frm.doc,
            args: { po_number: frm.doc.order_barcode },
            callback: function(r) {
                frm.set_value('order_barcode', '')
                if (r.message) {
                    let in_table = false
                    frm.doc.batch_order.forEach(row => {
                        if (row.production_order == r.message.production_order) {
                            row.status = r.message.status
                            in_table = true
                        }
                    });
                    if (!in_table) {
                        let in_empty_row = false
                        frm.doc.batch_order.forEach(row => {
                            if (!row.production_order && !in_empty_row) {
                                row.status = r.message.status
                                row.production_order = r.message.production_order
                                in_empty_row = true
                            }
                        });

                        if (!in_empty_row) {
                            let row = frm.add_child('batch_order')
                            row.status = r.message.status
                            row.production_order = r.message.production_order
                        }
                    }
                }
                frm.refresh_field('order_barcode')
                frm.refresh_field('batch_order')
            }
        })
    },
    production_route: function(frm) {
        if (!frm.doc.production_route || frm.doc.production_route == "") {
            frm.clear_table('tray_steps')
            frm.refresh_fields();
            return
        } else {
            frm.clear_table('tray_steps')
            frappe.model.with_doc("Production Route", frm.doc.production_route, function() {
                var tabletransfer = frappe.model.get_doc("Production Route", frm.doc.production_route)
                $.each(tabletransfer.route_steps, function(index, row) {
                    var d = frm.add_child("tray_steps");
                    d.production_step = row.production_step
                    d.issue_step = row.issue_step
                    d.labor = row.labor;
                    d.overhead = row.overhead;
                });
                frm.refresh_field("tray_steps");
            });
        }
    }
});

frappe.ui.form.on('Tray Step', {
    finish_step: function(frm, cdt, cdn) {
        if (frm.doc.docstatus != 1) {
            frappe.throw('Please Submit Document before Update the Step!')
            return
        } else {
            const row = locals[cdt][cdn]

            frappe.call({
                method: 'update_production_step',
                doc: frm.doc,
                freeze: true,
                freeze_message: __("update date process starting"),
                args: {
                    row: row.idx,
                    date: frappe.datetime.nowdate()
                },
                callback: function(r) {
                    if (!r.exc) {
                        frm.reload_doc()
                    }
                }
            })
        }
    }
})