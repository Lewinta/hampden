import frappe

def execute():
    if frappe.db.exists("Custom Field", "Customer-transform_configuration_section"):
        frappe.delete_doc('Custom Field', 'Customer-transform_configuration_section')
    
    if frappe.db.exists("Custom Field", "Customer-transformation_method"):
        frappe.delete_doc('Custom Field', 'Customer-transformation_method')

    frappe.db.commit()