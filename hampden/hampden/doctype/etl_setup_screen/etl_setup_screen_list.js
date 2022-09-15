frappe.listview_settings['ETL Setup Screen'] = {
	add_fields: ["status"],
	get_indicator: function(doc) {
		var status_color = {
			"New": "grey",
			"Pairing needed": "yellow",
			"Ready for PO creation": "blue",
			"Processed": "green",
			"Partially Processed": "orange"

		};
		return [__(doc.status), status_color[doc.status], "status,=,"+doc.status];
	},
};
