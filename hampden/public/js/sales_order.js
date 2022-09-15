// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

{% include 'erpnext/selling/sales_common.js' %}

frappe.ui.form.on("Sales Order", {
    setup: function (frm) {
        frm.custom_make_buttons = {
            'Production Order': "Production Order"
        }
    },
    refresh: function (frm) {
        let allow_delivery = false;
        if (frm.doc.docstatus == 1) {
            if (frm.doc.status !== 'Closed') {
                allow_delivery = frm.doc.items.some(item => item.delivered_by_supplier === 0 && item.qty > flt(item.delivered_qty))
                    && !frm.doc.skip_delivery_note

                if (flt(frm.doc.per_delivered, 6) < 100 && ["Sales", "Shopping Cart"].indexOf(frm.doc.order_type) !== -1 && allow_delivery) {
                    frm.add_custom_button(__('Prodcution Order'), () => frm.trigger('make_prodcution_order'), __('Create'));
                }
            }
        }
    },
     
    make_prodcution_order(frm) {
        frm.call({
            // doc: frm.doc,
            method: 'hampden.api.get_production_order_items',
            args: {
                sales_order: frm.doc.name
            },
            callback: function (r) {
                if (!r.message) {
                    frappe.msgprint({
                        title: __('Production Order not created'),
                        message: __('No Items with Bill of Materials to Manufacture'),
                        indicator: 'orange'
                    });
                    return;
                }
                else if (!r.message) {
                    frappe.msgprint({
                        title: __('Production Order not created'),
                        message: __('Production Order already created for all items with BOM'),
                        indicator: 'orange'
                    });
                    return;
                } else {
                    const fields = [{
                        label: 'Items',
                        fieldtype: 'Table',
                        fieldname: 'items',
                        description: __('Select BOM and Qty for Production'),
                        fields: [{
                            fieldtype: 'Read Only',
                            fieldname: 'item_code',
                            label: __('Item Code'),
                            in_list_view: 1
                        }, {
                            fieldtype: 'Link',
                            fieldname: 'bom',
                            options: 'BOM',
                            reqd: 1,
                            label: __('Select BOM'),
                            in_list_view: 1,
                            get_query: function (doc) {
                                return { filters: { item: doc.item_code } };
                            }
                        }, {
                            fieldtype: 'Float',
                            fieldname: 'pending_qty',
                            reqd: 1,
                            label: __('Qty'),
                            in_list_view: 1
                        }, {
                            fieldtype: 'Data',
                            fieldname: 'sales_order_item',
                            reqd: 1,
                            label: __('Sales Order Item'),
                            hidden: 1
                        }],
                        data: r.message,
                        get_data: () => {
                            return r.message
                        }
                    }]
                    var d = new frappe.ui.Dialog({
                        title: __('Select Items to Manufacture'),
                        fields: fields,
                        primary_action: function () {
                            var data = d.get_values();
                            frm.call({
                                method: 'hampden.api.make_production_orders',
                                args: {
                                    items: data,
                                    company: frm.doc.company,
                                    sales_order: frm.docname,
                                    project: frm.project
                                },
                                freeze: true,
                                callback: function (r) {
                                    if (r.message) {
                                        frappe.msgprint({
                                            message: __('Production Orders Created: {0}',
                                                [r.message.map(function (d) {
                                                    return repl('<a href="#Form/Production Order/%(name)s">%(name)s</a>', { name: d })
                                                }).join(', ')]),
                                            indicator: 'green'
                                        })
                                    }
                                    d.hide();
                                }
                            });
                        },
                        primary_action_label: __('Create')
                    });
                    d.show();
                }
            }
        });
    },
});