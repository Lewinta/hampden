// Copyright (c) 2022, ahmadragheb and contributors
// For license information, please see license.txt

frappe.ui.form.on('Design Order', {
    setup: function(frm) {
        frm.doc.date = frappe.datetime.now_datetime()
        frm.get_docfield("batch_order").allow_bulk_edit = 1;
    },
    refresh(frm) {
        if (frm.doc.docstatus == 1) {
            frm.add_custom_button('Add to tray', (ev) => {
                let data = [];
                const fields = [{
                    fieldtype: 'Link',
                    fieldname: "production_order",
                    options: 'Production Order',
                    in_list_view: 1,
                    read_only: 0,
                    disabled: 0,
                    label: __('Production Order')
                }, {
                    fieldtype: 'Link',
                    fieldname: 'item_code',
                    options: 'Item',
                    read_only: 1,
                    in_list_view: 1,
                    label: __('Item Code'),
                    reqd: 1,
                }, {
                    fieldtype: 'Float',
                    fieldname: "qty",
                    default: 0,
                    read_only: 1,
                    in_list_view: 1,
                    label: __('Qty'),
                }, {
                    fieldtype: 'Link',
                    fieldname: "panel",
                    options: "Panel",
                    default: 0,
                    read_only: 1,
                    in_list_view: 1,
                    label: __('Panel')
                }];

                const dialog = new frappe.ui.Dialog({
                    title: __("Add to tray"),
                    fields: [{
                        fieldname: "tray_orders",
                        fieldtype: "Table",
                        label: "Production Orders",
                        cannot_add_rows: true,
                        in_place_edit: true,
                        reqd: 1,
                        read_only: 1,
                        data: data,
                        get_data: () => {
                            return data;
                        },
                        fields: fields
                    }, ],
                    primary_action: function() {
                        const tray_orders = this.get_values()["tray_orders"].filter((order) => !!order.production_order);
                        console.log(tray_orders);
                        this.hide();
                    },
                    primary_action_label: __('Add')
                });

                frm.doc.batch_order.forEach(d => {
                    console.log(d);
                    dialog.fields_dict.tray_orders.df.data.push({
                        "production_order": d.production_order,
                        "item_code": d.item_code,
                        "qty": d.quantity,
                        "panel": d.panel
                    });
                    data = dialog.fields_dict.tray_orders.df.data;
                    dialog.fields_dict.tray_orders.grid.refresh();
                })
                dialog.show();
            })
        }
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
                            in_table = true
                        }
                    });
                    if (!in_table) {
                        let in_empty_row = false
                        frm.doc.batch_order.forEach(row => {
                            if (!row.production_order && !in_empty_row) {
                                row.production_order = r.message.production_order
                                row.quantity = r.message.quantity || 1
                                row.item_code = r.message.item_code
                                row.personalization = r.message.personalization
                                in_empty_row = true
                            }
                        });

                        if (!in_empty_row) {
                            let row = frm.add_child('batch_order')
                            row.production_order = r.message.production_order
                            row.quantity = r.message.quantity || 1
                            row.item_code = r.message.item_code
                            row.personalization = r.message.personalization
                                // row = r.message
                        }
                    } else {

                        let row = frm.add_child('batch_order')
                        row.production_order = r.message.production_order
                        row.quantity = r.message.quantity || 1
                        row.item_code = r.message.item_code
                        row.personalization = r.message.personalization
                    }
                }
                frm.refresh_field('order_barcode')
                frm.refresh_field('batch_order')
            }
        })
    },
    production_route: function(frm) {
        if (!frm.doc.production_route || frm.doc.production_route == "") {
            frm.clear_table('production_steps')
            frm.refresh_fields();
            return
        } else {
            frm.clear_table('production_steps')
            frappe.model.with_doc("Production Route", frm.doc.production_route, function() {
                var tabletransfer = frappe.model.get_doc("Production Route", frm.doc.production_route)
                $.each(tabletransfer.route_steps, function(index, row) {
                    if (flt(row.in_design) == 1) {
                        var d = frm.add_child("production_steps");
                        d.production_step = row.production_step
                        d.issue_step = row.issue_step
                        d.labor = row.labor;
                        d.overhead = row.overhead;
                    }
                });
                frm.refresh_field("production_steps");
            });
        }
    }
});