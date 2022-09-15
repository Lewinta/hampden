# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "hampden"
app_title = "Hampden"
app_publisher = "ahmadragheb"
app_description = "ERPnext implementation for Hampden"
app_icon = "octicon octicon-tools"
app_color = "grey"
app_email = "Ahmedragheb75@gmail.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/hampden/css/hampden.css"
# app_include_js = "/assets/hampden/js/hampden.js"

# include js, css files in header of web template
# web_include_css = "/assets/hampden/css/hampden.css"
# web_include_js = "/assets/hampden/js/hampden.js"
app_include_js = [
    "/assets/hampden/js/hampden.min.js"
]

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Item": "public/js/item.js",
    "Sales Order": "public/js/sales_order.js",
    "Sales Invoice": "public/js/sales_invoice.js",
    "Work Order": "public/js/work_order.js",
    "Purchase Receipt": "public/js/purchase_receipt.js"
}

# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "hampden.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "hampden.install.before_install"
# after_install = "hampden.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "hampden.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Item": {
        "on_change": "hampden.api.update_bom_on_change",
        "validate": "hampden.api.validate_item",
        "on_update": "hampden.api.on_update_item"
    },
    "Purchase Receipt": {
        "on_submit": "hampden.api.update_all_items_rates",
        "on_cancel": "hampden.api.update_all_items_rates"
    },
    "Delivery Note": {
        "on_submit": "hampden.api.update_all_items_rates",
        "on_cancel": "hampden.api.update_all_items_rates"
    },
    "Purchase Invoice": {
        "on_submit": "hampden.api.update_all_items_rates",
        "on_cancel": "hampden.api.update_all_items_rates"
    },
    "Sales Invoice": {
        "on_submit": "hampden.api.update_all_items_rates",
        "on_cancel": "hampden.api.update_all_items_rates"
    },
    # "Stock Ledger Entry":{
    #     "on_submit": "hampden.api.update_all_items_rates",
    #     "on_cancel": "hampden.api.update_all_items_rates"
    # },
    "Stock Entry":{
        # "on_submit": "hampden.api.jv_for_work_orders",
        # "on_cancel": "hampden.api.jv_for_work_orders",
        "validate": "hampden.api.validate_stock_entry",
        "on_submit": "hampden.api.submit_stock_entry",
        "on_cancel": "hampden.api.cancel_stock_entry",
    },
    "Journal Entry":{
        "on_submit": "hampden.api.submit_journal_entry",
        "on_cancel": "hampden.api.cancel_journal_entry",
    },
    "File": {
        "after_insert": "hampden.api.test_email"
    }
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"hampden.tasks.all"
# 	],
# 	"daily": [
# 		"hampden.tasks.daily"
# 	],
# 	"hourly": [
# 		"hampden.tasks.hourly"
# 	],
# 	"weekly": [
# 		"hampden.tasks.weekly"
# 	]
# 	"monthly": [
# 		"hampden.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "hampden.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "hampden.event.get_events"
# }
override_whitelisted_methods = {
	"erpnext.stock.get_item_details.get_item_details": "hampden.api.get_item_details",
	"erpnext.controllers.item_variant.create_variant": "hampden.whitelist.create_variant"
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Work Order": "hampden.api.get_wo_dashboard_data"
# }
override_doctype_dashboards = {
	"Sales Order": "hampden.api.get_sales_order_dashboard_data"
}

fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            [
                "name",
                "in",
                [
                    "Item-metal_type",
                    "Item-hampden_manufacturing",
                    "Item-production_route",
                    "Item-production_item_table",
                    "Item-total_labor",
                    "Item-column_break_40",
                    "Item-total_overhead",
                    "Item-materials",
                    "Item-items",
                    "Item-column_break_38",
                    "Item-scrap",
                    "Item-production_scrap_item",
                    "Item-costing",
                    "Item-total_production_route",
                    "Item-raw_material_cost",
                    "Item-scrap_material_cost",
                    "Item-total_cost",
                    "Item-intrinsic_material_cost",
                    "Item-fabrication_cost",
                    "Item-cutting_loss_cost",
                    
                    "Purchase Receipt-lock_section",
                    "Purchase Receipt-lock_date",
                    "Purchase Receipt-gold_lock",
                    "Purchase Receipt-silver_lock",
                    "Purchase Receipt-column_break_42",
                    "Purchase Receipt-gm_14k",
                    "Purchase Receipt-gm_10k",
                    "Purchase Receipt-ssgm",
                    "Purchase Receipt-total_invoiced",
                    
                    "Purchase Receipt Item-is_dependent_item",
                    "Purchase Receipt Item-link_to",
                    "Purchase Receipt Item-metal_type",

                    "Work Order-ignore_bom",
                    "Work Order-work_order_jv",
                    
                    "Journal Entry-work_order",

                    "BOM Item-issue_step",
                    "BOM Explosion Item-issue_step",
                    "BOM Scrap Item-issue_step",

                    "Work Order Item-issue_step",

                    "Stock Entry Detail-issue_step",
                    "Stock Entry-production_order",
                    "Stock Entry Detail-production_detail",
                    "Stock Entry Detail-production_order",
                    "Stock Entry Detail-hampden_production",
                    "Stock Entry Detail-is_scrap",

                    "Sales Invoice-production_invoice",
                    "Sales Invoice-production_order",

                    "Item Variant Settings-add_dashes",
                    "Item Variant Settings-include_temp_name",

                    "Item Attribute Value-attribute_short_value",
                    "Item Attribute Value-add_to_item_code",

                    "Sales Order-prs_section",
                    "Sales Order-personalization"

                    "Sales Order-against_customer_po"
                ]
            ]
        ]
    },
    {
        "dt": "Property Setter",
        "filters": [
            [
                "name",
                "in",
                [
                    "Purchase Receipt Item-rate-precision",
                    "Purchase Receipt Item-amount-precision",
                    "Stock Entry Detail-item_group-in_list_view",
                    "Journal Entry Account-reference_type-options"
                ]
            ]
        ]
    },
    {
        "dt": "Notification",
        "filters": [
            [
                "name",
                "in",
                [
                    "Notify file to process field changes",
                    "Notify Creating Customer PO",
                    "Notify Create Pairing Item",
                    "Notify Edit Configration in Pairing Item Doc",
                    "Notify update External Item in Pairing Item Doc"
                ]
            ]
        ]
    }
]
