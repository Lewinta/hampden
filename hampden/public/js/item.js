frappe.provide("erpnext.item");

frappe.ui.form.on("Item", {
    setup: function (frm) {
        frm.set_query("item_code", "items", function () {
            return {
                query: "erpnext.controllers.queries.item_query",
                filters: [
                    ["Item", "name", "!=", cur_frm.doc.item_code],
                    ["Item", "is_stock_item", "=", 1]
                ]
            };
        });

        frm.set_query("bom_no", "items", function (doc, cdt, cdn) {
            var d = locals[cdt][cdn];
            return {
                filters: {
                    'item': d.item_code,
                    'is_active': 1,
                    'docstatus': 1
                }
            };
        });
    },
    onload_post_render: function (frm) {
        frm.get_field("items").grid.set_multiple_add("item_code", "qty");
    },
    production_route: function (frm) {
        if (!frm.doc.production_route || frm.doc.production_route == "") {
            frm.clear_table('production_item_table')
            frm.trigger('update_production_totals')
            frm.refresh_fields();
            return
        } else {
            frappe.model.with_doc("Production Route", frm.doc.production_route, function () {
                var tabletransfer = frappe.model.get_doc("Production Route", frm.doc.production_route)
                $.each(tabletransfer.route_steps, function (index, row) {
                    var d = frm.add_child("production_item_table");
                    d.production_step = row.production_step
                    d.issue_step = row.issue_step
                    d.labor = row.labor;
                    d.overhead = row.overhead;

                    d.total_labor = d.labor * d.qty;
                    d.total_overhead = d.overhead * d.qty;
                    d.total = d.total_labor + d.total_overhead

                });
                frm.refresh_field("production_item_table");

                frm.trigger('update_production_totals')
            });
        }
    },
    update_production_totals: function (frm) {
        let total_overhead = 0
        let total_labor = 0
        let total_production_route = 0
        frm.doc.production_item_table.forEach(row => {
            total_overhead += parseFloat(row.total_overhead || 0)
            total_labor += parseFloat(row.total_labor || 0)
            total_production_route += parseFloat(row.total || 0)

        });
        frm.set_value('total_overhead', total_overhead)
        frm.set_value('total_labor', total_labor)
        frm.set_value('total_production_route', total_production_route)
        frm.refresh_field("total_labor");
        frm.refresh_field("total_overhead");
        frm.refresh_field("total_production_route");
        frm.trigger('update_costs')
    },

    update_costs: function (frm) {
        let production_route = 0
        let raw_material_cost = 0
        let scrap_cost = 0
        let total_cost = 0

        let intrinsic_material_cost = 0
        let fabrication_cost = 0
        let cutting_loss_cost = 0

        frm.doc.items.forEach(row => {
            if (row.item_type == "Independent")
                intrinsic_material_cost += (row.amount || 0)

            if (row.item_type == "Dependent")
                fabrication_cost += (row.amount || 0)

            if (row.item_type == "Cutting Loss")
                cutting_loss_cost += (row.amount || 0)

            raw_material_cost += (row.amount || 0)
        });
        frm.doc.production_scrap_item.forEach(row => {
            scrap_cost += (row.amount || 0)
        });
        frm.doc.production_item_table.forEach(row => {
            production_route += (row.total || 0)
        });

        // total_cost = raw_material_cost - scrap_cost + production_route
        total_cost = raw_material_cost + production_route

        frm.set_value('total_production_route', production_route)
        frm.set_value('raw_material_cost', raw_material_cost)
        frm.set_value('intrinsic_material_cost', intrinsic_material_cost)
        frm.set_value('fabrication_cost', fabrication_cost)
        frm.set_value('cutting_loss_cost', cutting_loss_cost)
        frm.set_value('scrap_material_cost', scrap_cost)
        frm.set_value('total_cost', total_cost)
        frm.refresh_fields()

    }
});

frappe.ui.form.on('Production Item Table', {
    qty: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        row.total_labor = row.labor * row.qty;
        row.total_overhead = row.overhead * row.qty;
        row.total = row.total_labor + row.total_overhead;

        frm.refresh_field("production_item_table");
        frm.trigger('update_production_totals')

    }
});

frappe.ui.form.on('Item Item', {
    item_code: function (frm, cdt, cdn) {
        var item = frappe.get_doc(cdt, cdn);

        if (item.item_code && item.item_code != "") {
            frappe.call({
                method: 'hampden.api.get_item_association_data',
                args: {
                    'item_code': item.item_code
                },
                callback: function (r) {
                    if (r && r.message) {
                        const rate = r.message.rate || 0
                        item.rate = rate
                        item.amount = rate * parseFloat(item.qty || 1)
                        // frm.refresh_field('items')
                        if (r.message.iat && r.message.iat.length > 0) {
                            item.item_type = "Independent"

                            r.message.iat.forEach(itm => {
                                if (itm.dependent) {
                                    itm = itm.dependent
                                    frm.add_child('items', {
                                        'item_code': itm.item_code,
                                        'dependent_percent': itm.dependent_percent,
                                        'qty': itm.qty,
                                        'amount': itm.amount,
                                        'uom': itm.uom,
                                        'stock_uom': itm.stock_uom,
                                        'item_name': itm.item_name,
                                        'description': itm.description,
                                        'item_type': itm.item_type,
                                        'independent': itm.independent,
                                        'rate': itm.rate,
                                    })
                                }
                                if (itm.cutting_loss) {
                                    itm = itm.cutting_loss
                                    frm.add_child('items', {
                                        'item_code': itm.item_code,
                                        'cutting_percent': itm.cutting_percent,
                                        'qty': itm.qty,
                                        'amount': itm.amount,
                                        'uom': itm.uom,
                                        'stock_uom': itm.stock_uom,
                                        'item_name': itm.item_name,
                                        'description': itm.description,
                                        'item_type': itm.item_type,
                                        'independent': itm.independent,
                                        'rate': itm.rate,
                                    })
                                }
                                if (itm.scrap_item) {
                                    itm = itm.scrap_item
                                    frm.add_child('production_scrap_item', {
                                        'item_code': itm.item_code,
                                        'item_name': itm.item_name,
                                        'independent': itm.independent,
                                        'scrap_percent': itm.scrap_percent,
                                        'stock_qty': itm.stock_qty,
                                        'amount': itm.amount,
                                        'stock_uom': itm.stock_uom,
                                        'description': itm.description,
                                        'item_type': itm.item_type,
                                        'rate': itm.rate,
                                    })
                                }

                            })
                            frm.refresh_field('items')
                            frm.refresh_field('production_scrap_item')
                        }
                        frm.trigger('update_costs')
                    }
                }
            })
        }
    },
    qty: function (frm, cdt, cdn) {
        var item = frappe.get_doc(cdt, cdn);
        item.amount = item.rate * item.qty
        if (item.item_code && item.item_code != "") {
            let dependent_qty = 0
            // Update Cutting Loss
            frm.doc.items.forEach(row => {
                if (item.item_type == "Independent" && row.independent == item.item_code && row.item_type == "Cutting Loss") {
                    row.qty = (item.qty || 0) * (row.cutting_percent || 0) / 100
                    dependent_qty += ((item.qty || 0) * (row.cutting_percent || 0) / 100)
                    row.amount = row.rate * ((item.qty || 0) * (row.cutting_percent || 0) / 100)
                }
            })

            // Update Scrap
            frm.doc.production_scrap_item.forEach(row => {
                if (item.item_type == "Independent" && row.independent == item.item_code && row.item_type == "Scrap") {
                    row.stock_qty = (item.qty || 0) * (row.scrap_percent || 0) / 100
                    dependent_qty += ((item.qty || 0) * (row.scrap_percent || 0) / 100)
                    row.amount = row.rate * ((item.qty || 0) * (row.scrap_percent || 0) / 100)
                }
            })

            // Update dependent
            frm.doc.items.forEach(row => {
                if (item.item_type == "Independent" && row.independent == item.item_code && row.item_type == "Dependent") {
                    dependent_qty += ((item.qty || 0) * (row.dependent_percent || 0) / 100)
                    row.qty = dependent_qty
                    row.amount = row.rate * dependent_qty
                }
            })
            frm.trigger('update_costs')
        }
    },
    rate: function (frm, cdt, cdn) {
        var item = frappe.get_doc(cdt, cdn);
        item.amount = item.rate * item.qty
        frm.trigger('update_costs')
    }
});

frappe.ui.form.on('Production Scrap Item', {
    stock_qty: function (frm, cdt, cdn) {
        var item = frappe.get_doc(cdt, cdn);
        item.amount = item.rate * item.stock_qty
        frm.trigger('update_costs')
    },
    rate: function (frm, cdt, cdn) {
        var item = frappe.get_doc(cdt, cdn);
        item.amount = item.rate * item.stock_qty
        frm.trigger('update_costs')
    }
});