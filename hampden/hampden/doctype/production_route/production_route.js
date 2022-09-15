// Copyright (c) 2021, ahmadragheb and contributors
// For license information, please see license.txt

frappe.ui.form.on('Production Route', {
	// refresh: function(frm) {

	// }
	update_totals: function (frm) {
		let totalLabor = 0
		let totalOverhead = 0
		frm.doc.route_steps.forEach(row => {
			totalLabor += parseFloat(row.labor)
			totalOverhead += parseFloat(row.overhead)
		})
		frm.set_value('total_overhead', totalOverhead)
		frm.set_value('total_labor', totalLabor)
		frm.refresh_field('total_labor')
		frm.refresh_field('total_overhead')
	}
});

frappe.ui.form.on('Production Route Table', {
	// refresh: function(frm) {

	// }
	add_route_steps: function (frm, cdt, cdn) {
		frm.trigger('update_totals')
	},
	remove_route_steps: function (frm, cdt, cdn) {
		frm.trigger('update_totals')
	},
	overhead: function (frm, cdt, cdn) {
		frm.trigger('update_totals')
	},
	labor: function (frm, cdt, cdn) {
		frm.trigger('update_totals')
	}
});
