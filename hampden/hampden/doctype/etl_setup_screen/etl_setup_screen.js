// Copyright (c) 2022, ahmadragheb and contributors
// For license information, please see license.txt

frappe.ui.form.on("ETL Setup Screen", {
	setup: function (frm) {
		$(`#file-container`).html("")
		$(cur_frm.fields_dict["etl_screen_history_log_table"].wrapper).html(`
			<div class="table_container">
				<table class="table table-bordered borderless" id="etl_screen_history_log_table"}>
					<thead>
					<tr>
						<th width="20%" class="th_borderless">User</th>
						<th width="80%" class="th_borderless">Changes</th>
					</tr>
					</thead>
					<tbody>
					</tbody>
				</table>
			</div>
		`);
	},
	refresh: function (frm) {
		if (!frm.doc.final_result){
			$(`#file-container`).html("")
		}
		frm.get_field("file_to_process").df.options = {
			restrictions: {
				allowed_file_types: [".csv", ".xls", ".xlsx"],
			}
		};

		if (frm.doc.final_result){
			$(cur_frm.fields_dict["processed_file"].wrapper).html(`
				<div id="file-container">
					<label class="control-label" style="padding-right: 0px;">File After Processing</label>
					<a href="${frm.doc.final_result}" id="attach" class ="attached-file">${frm.doc.final_result}</a>
				</div>
			`)
		}
		
		frm.trigger("render_history_log")		
		frm.trigger("processed_file_validation")

		// Hide delete and add row btns in child table
		frm.fields_dict.processed_file_validation_log.grid.grid_buttons.addClass("hidden")
	},
	customer: function (frm) {
		if (!frm.doc.customer) {
			frm.doc.transform_method = "";
			frm.doc.file_to_process = "";
		}
		frm.refresh_fields();
	},
	process_file: function(frm){
		if (frm.doc.file_to_process){
			frappe.call({
				method: "start_process_file",
				doc: frm.doc,
				callback: function (r) {
					$(cur_frm.fields_dict["processed_file"].wrapper).html(`
						<div id="file-container">
							<label class="control-label" style="padding-right: 0px;">File After Processing</label>
							<a href="${frm.doc.final_result}" id="attach" class ="attached-file">${frm.doc.final_result}</a>
						</div>
					`)
	
					frm.refresh_field("process_file")
					frm.refresh_field("processed_file_table")
					frm.refresh_field("processed_file_table")
					frm.trigger("processed_file_validation")
					frm.refresh_field("processed_file_validation_log")
					frm.reload_doc()
				}
			})
		} else {
			frm.doc.status = "New"
		}
	},
	file_to_process: function (frm) {
		if (!frm.doc.file_to_process){
			frm.doc.final_result = ""
			$(`#file-container`).html("")
			frm.doc.processed_file_table = []
			frm.doc.processed_file_validation_log = []
		}else {
			frappe.call({
				method: "add_history_log",
				doc: frm.doc,
				args: {
					msg: "Attached File" + frm.doc.file_to_process + " " + " at " + " " + frappe.datetime.get_today()
				},
				callback: function (r) {
					frm.trigger("render_history_log")
					frm.reload_doc()
				}
			})
		}
	},

	// New Devs
	processed_file_validation: function(frm) {
		$("div[data-fieldname='row_status'] .static-area").each(function(){
			let text = $(this).text()
			if(text == "Ready to be processed"){
				$(this).addClass("text-success bold")
			}
			if(text == "Failed to pair"){
				$(this).addClass("text-danger bold")
			}
			if(text == "Paired Manually"){
				$(this).addClass("text-primary bold")
			}
		})
	},
	create_customer_po: function(frm){
		let rows = frm.get_field('processed_file_validation_log').grid.get_selected_children()
		if(rows.length){
			rows.forEach((row, index) => {
				if(row.row_status == "Failed to pair") {
					let msg = "Row " + (index + 1) + " Cant created in Customer Po Please fix or uncheck this row" 
					frappe.throw(msg)
				}
			});
			frappe.call({
				method: "create_customer_po",
				doc: frm.doc,
				args:{
					data: rows
				},
				freeze: true,
				freeze_message: "Creating Customer PO",
				callback: function (r) {
					if(r.message){
						frm.reload_doc()
						frm.refresh_field("customer_po")
						frappe.set_route('Form', 'Customer PO', r.message.customer_po);
					}
				}
			});
		}else {
			frappe.throw("Please Select rows from Processed File Validation Log table to Create Customer PO")
		}
	},
	render_history_log: function(frm){
		$(`#etl_screen_history_log_table tbody`).html("")
		if(frm.doc.etl_screen_history_log){
			frm.doc.etl_screen_history_log.forEach(row => {
				$(`#etl_screen_history_log_table tbody`).append(`
					<tr>
						<td class="bold">${row.user}</td>
						<td>${row.change_msg}</td>
					</tr>
				`)
			});
		}
		
	}
});

frappe.ui.form.on("Processed File Validation Log Table", {
	external_item: function(frm,cdt,cdn) {
		var row = locals[cdt][cdn];
		// Update Pairing Item Doc with new external item name 
		if(row.internal_item){
			frappe.call({
				method: "update_pair_doc",
				doc: frm.doc,
				freeze: true,
				freeze_message: "Updating Pairing Item Doc",
				args : {
					idx: row.idx,
					ex_item: row.external_item,
					doc_name: row.reference_pair_doc,
					process_row_id: row.processed_table_row_id
				},
				callback: function (r) {
					if(!r.exc) {
						frm.reload_doc()
					}
				}
			})
		} else {
			// Update Processed File table row with new external item name 
			frappe.call({
				method: "update_processed_file_table",
				doc: frm.doc,
				freeze: true,
				freeze_message: "Updating Processed File table",
				args : {
					ex_item: row.external_item,
					doc_name: "",
					process_row_id: row.processed_table_row_id,
					update_pair: false
				},
				callback: function (r) {
					if(!r.exc) {
						frm.reload_doc()
					}
				}
			})
		}
	},
	internal_item: function(frm,cdt,cdn) {
		var row = locals[cdt][cdn];
		if(row.internal_item){
			frappe.call({
				method: "create_pair_doc",
				doc: frm.doc,
				freeze: true,
				freeze_message: "Creating Pairing Item Doc",
				args : {
					idx: row.idx,
					ex_item: row.external_item,
					in_item: row.internal_item,
					transformation_method: frm.doc.transform_method,
					doc_name: row.name,
					configuration: row.configuration
				},
				callback: function (r) {
					if(!r.exc) {
						frm.trigger("render_history_log")
						frm.trigger("processed_file_validation")
						frm.reload_doc()
					}
				}
			})
		}
	},
	configuration: function(frm,cdt,cdn) {
		var row = locals[cdt][cdn];
		if(row.configuration && row.internal_item){
			frappe.call({
				method: "edit_pair_doc",
				doc: frm.doc,
				freeze: true,
				freeze_message: "Editing Pairing Item Doc Configuration",
				args : {
					idx: row.idx,
					ex_item: row.external_item,
					in_item: row.internal_item,
					transformation_method: frm.doc.transform_method,
					pair_doc_name: row.reference_pair_doc,
					configuration: row.configuration
				},
				callback: function (r) {
					if(!r.exc) {
						frm.reload_doc()
					}
				}
			})
		}else {
			row.configuration = ""
			frappe.throw("Please Fill Internal Item Field before")
		}
	},
	form_render(frm, cdt, cdn){
        frm.fields_dict.processed_file_validation_log.grid.wrapper.find('.grid-delete-row').hide();
        frm.fields_dict.processed_file_validation_log.grid.wrapper.find('.grid-duplicate-row').hide();
        frm.fields_dict.processed_file_validation_log.grid.wrapper.find('.grid-move-row').hide();
        frm.fields_dict.processed_file_validation_log.grid.wrapper.find('.grid-append-row').hide();
        frm.fields_dict.processed_file_validation_log.grid.wrapper.find('.grid-insert-row-below').hide();
        frm.fields_dict.processed_file_validation_log.grid.wrapper.find('.grid-insert-row').hide();
    }
})