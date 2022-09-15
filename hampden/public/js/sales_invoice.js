frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {
        if (frm.doc.docstatus == 1 && frm.doc.outstanding_amount != 0
            && !(cint(frm.doc.is_return) && frm.doc.return_against) && cint(frm.doc.production_invoice) == 1 && frm.doc.production_order) {
            frm.add_custom_button(
                __('Production Payment'),
                function () {
                    return frappe.call({
                        method: "hampden.api.get_payment_entry_against_invoice",
                        args: {
                            "dt": frm.doc.doctype,
                            "dn": frm.doc.name
                        },
                        callback: function (r) {
                            if(r.message && r.message == 'Done')
                            frm.reload_doc()
                            // var doclist = frappe.model.sync(r.message);
                            // frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
                            // cur_frm.refresh_fields()
                        }
                    });
                }, __('Create')
            );

            frm.page.set_inner_btn_group_as_primary(__('Create'));
        }
    }
})