# Copyright (c) 2022, ahmadragheb and contributors
# For license information, please see license.txt

from cmath import log
from telnetlib import STATUS
from unicodedata import name
from warnings import filters
import frappe

from frappe.model.document import Document
from frappe.utils.csvutils import read_csv_content, UnicodeWriter
from frappe.utils.xlsxutils import (
    read_xlsx_file_from_attached_file,
    read_xls_file_from_attached_file,
)
from frappe.utils import today, cstr, flt


class ETLSetupScreen(Document):
    def validate(self):
        self.set_doc_status()

    @frappe.whitelist()
    def start_process_file(self):
        data = None
        errors = []
        extension = None
        content = None
        new_file_url = ""

        # GET File Doc , Extension , Content
        if frappe.db.exists("File", {"file_url": self.file_to_process}):
            file_doc = frappe.get_doc(
                "File", {"file_url": self.file_to_process})
            parts = file_doc.get_extension()
            extension = parts[1]
            extension = extension.lstrip(".")
            content = file_doc.get_content()

        # Check File Extension
        if extension:
            check_file_extension(extension)

        # Read File content
        if content:
            data = read_file_content(extension, content)
        else:
            frappe.throw("Can't process file, becaues file is Empty")

        # Check and validated data
        if data:
            content_list = data[4:]
            writer = self.process_file_content(content_list)
            if writer:
                file_doc = self.create_file_doc(writer)
                new_file_url = frappe.db.get_value(
                    "File", file_doc.name, "file_url")
                self.final_result = new_file_url

        self.save()
        

        # Validate Processed File Contant 
        self.validate_processed_file_content()
        
        return

    def process_file_content(self, content_list):
        new_data = []
        header_row = [
            "Number", "Line", "Item", "Supplier Item", "Quantity", "Description",
            "Left Letter", "Center Letter", "Right Letter", "Chain Length",
            "Metal", "UOM", "Price", "Amount", "Ship To", "Ship To Address", "Ship To City", "Ship To State", "Ship To Zip"
        ]
        writer = UnicodeWriter()
        writer.writerow(header_row)

        for row in content_list:
            for i in range(len(row)):
                if row[i] == None:
                    row[i] = ""
                row[i] = str(row[i])

            e = row[12]
            e = e[len(e)-1] if len(e) > 0 else ""

            number = row[0]+"-"+row[1]
            line = row[2]
            item = row[3]
            sup_item = row[4]
            qty = row[5]
            desc = row[6]
            left_letter = row[8]+" "+row[9]+" "+row[10]+" "+row[13]+"  " + \
                row[14]+" "+row[15]+" "+row[16]+" " + \
                row[17]+" "+row[18]+" "+row[19]
            center_letter = ""
            right_letter = ""
            chain_len = ""
            if row[11] or row[12]:
                chain_len = row[11]+" "+row[12] + '"'
            metal = row[7]
            uom = row[20]
            price = row[21]
            amount = row[22]
            shipt_to = row[23]
            ship_add = row[24]
            ship_city = row[25]
            ship_state = row[26]
            ship_zip = row[27]

            data_row = [
                number, line, item, sup_item, qty, desc, left_letter, center_letter, right_letter, chain_len,
                metal, uom, price, amount, shipt_to, ship_add, ship_city, ship_state, ship_zip
            ]
            writer.writerow(data_row)

            # Add Processed File Data to Processed File Table
            self.append("processed_file_table", {
                    "number": number,
                    "line": line,
                    "item": item,
                    "supplier_item": sup_item,
                    "quantity": qty,
                    "description": desc,
                    "left_letter": left_letter,
                    "center_letter": center_letter,
                    "right_letter": right_letter,
                    "chain_length": chain_len,
                    "metal": metal,
                    "uom": uom,
                    "price": price,
                    "amount": amount,
                    "price": price,
                    "amount": amount,
                    "ship_to": shipt_to,
                    "ship_to_address": ship_add,
                    "ship_to_city": ship_city,
                    "ship_to_state": ship_state,
                    "ship_to_zip": ship_zip
                }
            )

        return writer

    def create_file_doc(self, writer):
        doc = frappe.get_doc({
            "doctype": "File",
            "file_name":  self.customer + "-" + today() + "- for import-" + ".csv",
            "attached_to_doctype": self.doctype,
            "attached_to_name": self.name,
            "content": cstr(writer.getvalue()),
            "is_private": True
        })

        doc.insert()

        return doc

    @frappe.whitelist()
    def create_customer_po(self, data):
        row_idx = ''
        if self.customer_po:
            prev_doc = frappe.get_doc("Customer PO", self.customer_po)
            prev_doc.cancel()
            
        doc = frappe.new_doc("Customer PO")
        doc.customer = self.customer
        doc.date = today()
        doc.delivery_date = today()
        total_qty = 0
        total = 0
        for row in data:
            row_doc = frappe.get_doc("Processed File table", row.get("processed_table_row_id"))
            doc.append("items", {
                "item_code": row.get("internal_item"),
                "item_name": frappe.db.get_value("Item", row.get("internal_item"), "item_name") or "",
                "line": row_doc.line,
                "supplier_item": row_doc.supplier_item or "",
                "description": row_doc.description or "",
                "left_letter": row_doc.left_letter or "",
                "center_letter": row_doc.center_letter or "",
                "right_letter": row_doc.right_letter or "",
                "chain_length": row_doc.chain_length or "",
                "metal": row_doc.metal or "",
                "qty": row_doc.quantity or 0,
                "uom": row_doc.uom or "",
                "rate": flt(row_doc.price) or 0,
                "amount": row_doc.amount * flt(row_doc.price),
                "ship_to": row_doc.ship_to,
                "ship_to_address": row_doc.ship_to_address,
                "ship_to_city": row_doc.ship_to_city,
                "ship_to_state": row_doc.ship_to_state,
                "ship_to_zip": row_doc.ship_to_zip
            })
            total_qty += row_doc.quantity
            total += flt(row_doc.price)
            idx = row.get('idx')
            row_idx += f"{idx}, "

        doc.total_quantity = total_qty
        doc.total = total

        doc.save()
        doc.submit()
        self.customer_po = doc.name
        self.set_doc_status
        
        msg = f"""
            Customer PO Created Successfuly for rows {row_idx} at {frappe.utils.now()}
        """
        
        self.add_history_log(msg)

        return {"customer_po": doc.name}

    # Validate Processed File Content 
    def validate_processed_file_content(self):
        data = self.processed_file_table

        if data:
            for row in data:
                status = ''
                msg = ''
                item = ''
                name = ''
                
                # Add UOM If it's Not found in system
                if row.uom:
                    if not frappe.db.exists("UOM", row.uom):
                        doc = frappe.new_doc("UOM")
                        doc.uom_name = row.uom
                        doc.save()
                    
                # Get Internal item for current External item form Item Pairing doctype
                if frappe.db.exists("Item Pairing", {"external_item_number": row.item}):
                    item, name, configuration = frappe.db.get_value("Item Pairing", {"external_item_number": row.item}, ['item_code', 'name', 'configuration'])
                    status = "Ready to be processed"
                else: 
                    status = "Failed to pair"

                self.append("processed_file_validation_log", {
                    "row_status": status,
                    "external_item": row.item,
                    "internal_item": item,
                    "configuration": "",
                    "reference_pair_doc": name,
                    "processed_table_row_id": row.name
                })
        else: 
            frappe.throw("Processed File Don't have any Data")
        
        self.set_doc_status()
        self.save()

    @frappe.whitelist()
    def update_pair_doc(self, idx, ex_item, doc_name, process_row_id):
        prev_ex_item = ''
        if frappe.db.exists("Item Pairing", doc_name):
            doc = frappe.get_doc("Item Pairing", doc_name)
            prev_ex_item = doc.external_item_number
            if doc.external_item_number != ex_item:
                doc.external_item_number = ex_item
                doc.save()
                self.edited_idx = idx
                self.update_processed_file_table(ex_item, doc_name, process_row_id, True)

    @frappe.whitelist()
    def update_processed_file_table(self, ex_item, doc_name=None, process_row_id=None, update_pair=None):
        prev_ex_item = ''
        if frappe.db.exists("Processed File table", process_row_id):
            doc = frappe.get_doc("Processed File table", process_row_id)
            prev_ex_item = doc.item
            if doc.item != ex_item:
                doc.item = ex_item
                doc.save()

                msg = ""
                if update_pair:
                    msg = f"""
                        External item Changed from {prev_ex_item} to {ex_item} in Processed File table and Item Pairing Doc {doc_name} at {frappe.utils.now()}
                    """
                else:
                    msg = f"""
                        External item Changed from {prev_ex_item} to {ex_item} in Processed File table at {frappe.utils.now()}
                    """
                self.add_history_log(msg)

    @frappe.whitelist()
    def create_pair_doc(self, idx, ex_item, in_item, transformation_method, doc_name, configuration=""):
        prev_status = ''
        new_status = "Paired Manually"
        pair_doc = frappe.new_doc("Item Pairing")
        pair_doc.transformation_method = transformation_method
        pair_doc.external_item_number = ex_item
        pair_doc.configuration = configuration
        pair_doc.item_code = in_item
        pair_doc.save()
        self.edited_idx = idx


        msg = f"""
            Create Item Pairing Doc for External item {ex_item} with internal item {in_item},
            Then change status from {prev_status} to {new_status} in row {idx} in Processed File Validation Log Table at {frappe.utils.now()}
        """
        
        self.add_history_log(msg)
        
        frappe.db.set_value("Processed File Validation Log Table", doc_name, "row_status", "Paired Manually")
        frappe.db.set_value("Processed File Validation Log Table", doc_name, "internal_item", in_item)
        frappe.db.set_value("Processed File Validation Log Table", doc_name, "reference_pair_doc", pair_doc.name)


    @frappe.whitelist()
    def edit_pair_doc(self, idx, ex_item, in_item, transformation_method, pair_doc_name, configuration=""):
        if pair_doc_name:
            pair_doc = frappe.get_doc("Item Pairing", pair_doc_name)
            pair_doc.configuration = configuration
            pair_doc.save()
            self.edited_idx = idx


        msg = f"""
            Update configuration in item pairing doc {pair_doc_name}  at {frappe.utils.now()}
        """
        
        self.add_history_log(msg)

    #ADD Any Change in Doc To history table
    @frappe.whitelist()
    def add_history_log(self, msg):
        self.append("etl_screen_history_log", {
            "user": frappe.session.user,
            "change_msg": msg
        })
        
        self.save()
        
        return

    @frappe.whitelist()
    def set_doc_status(self):
        status = "New"

        if len(self.processed_file_validation_log):
            if self.customer_po:
                for row in self.processed_file_validation_log:
                    if row.row_status == "Failed to pair":
                        status = "Partially Processed"
                        break
                    else:
                        status = "Processed"
            else:
                for row in self.processed_file_validation_log:
                    if row.row_status == "Failed to pair":
                        status = "Pairing needed"
                        break
                    else:
                        status = "Ready for PO creation"
        
        self.status = status

def read_file_content(extension, content):
    if extension == "csv":
        data = read_csv_content(content)
    elif extension == "xlsx":
        data = read_xlsx_file_from_attached_file(fcontent=content)
    elif extension == "xls":
        data = read_xls_file_from_attached_file(content)

    return data


def check_file_extension(extension):
    if extension not in ["csv", "xlsx", "xls"]:
        frappe.throw("Process File should be of type .csv, .xlsx or .xls")
