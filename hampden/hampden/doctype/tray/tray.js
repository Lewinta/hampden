// Copyright (c) 2021, ahmadragheb and contributors
// For license information, please see license.txt

frappe.ui.form.on('Tray', {
	refresh: function(frm){
		if(frm.doc.docstatus == 1)
		$(frm.wrapper).find('.barcode-wrapper.border').css({
			'display': 'none'
		});
		
		$(frm.wrapper).find('div[data-fieldtype="Barcode"] .control-input-wrapper').css({
			'text-align': 'center'
		});
	},
	tray_barcode: function(frm){
		frm.set_value('barcode', frm.doc.tray_barcode)
		frm.refresh_field('barcode')
	}
});
