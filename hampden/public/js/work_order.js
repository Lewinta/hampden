// erpnext.work_order.make_se = function (frm, purpose) {
//     this.show_prompt_for_qty_input(frm, purpose)
//         .then(data => {
//             return frappe.xcall('hampden.api.make_stock_entry', {
//                 'work_order_id': frm.doc.name,
//                 'purpose': purpose,
//                 'qty': data.qty
//             });
//         }).then(stock_entry => {
//             frappe.model.sync(stock_entry);
//             frappe.set_route('Form', stock_entry.doctype, stock_entry.name);
//         });
// }
// frappe.ui.form.on("Work Order", {
//     refresh: function (frm) {
//         if (frm.doc.ignore_bom == 1) {
//             frm.toggle_reqd('bom_no', 0)
//         } else {
//             frm.toggle_reqd('bom_no', 1)
//         }
//     }
// })