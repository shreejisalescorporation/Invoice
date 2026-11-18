import os
import unittest
from datetime import datetime
import json
import re
from unittest.mock import Mock, patch

os.environ.setdefault("FLASK_SECRET_KEY", "test-session-secret")
os.environ.setdefault("WTF_CSRF_SECRET_KEY", "test-csrf-secret")
os.environ.setdefault("FLASK_USERS_JSON", "{}")

import app


class CustomerInvoiceDetailsTests(unittest.TestCase):
    def generate_ply_invoice(self, item_values, form_values=None):
        customer_details = {
            "name": "Customer",
            "customer_type": "business",
            "gst_number": "24AVQPS7090F1Z2",
            "address": "",
            "address_lines": [],
            "mobile": "",
            "email": "",
        }
        serialized_items = [
            values if len(values) == 12 else [*values, "9", "9", "0"]
            for values in item_values
        ]
        data = {
            "chcharge": "0",
            "items[]": [json.dumps(values) for values in serialized_items],
        }
        data.update(form_values or {})
        with app.app.test_request_context(
            "/generate",
            method="POST",
            data=data,
        ):
            with (
                patch.object(app, "_form_date", return_value=datetime(2026, 11, 1)),
                patch.object(
                    app,
                    "_form_customer",
                    return_value="00000000-0000-0000-0000-000000000001",
                ),
                patch.object(
                    app, "get_customer_invoice_details", return_value=customer_details
                ),
            ):
                return app.generate_invoice()

    def test_formats_split_address_and_contact_fields(self):
        details = app._format_customer_invoice_details({
            "address_line_1": "12 Main Road",
            "address_line_2": "Building B",
            "area_landmark": "Near the station",
            "city_village_district": "Ahmedabad",
            "state": "Gujarat",
            "pincode": "380001",
            "mobile": "9876543210",
            "email": "customer@example.com",
            "customer_id": "customer-1",
            "customer_type": "business",
            "name": "Customer",
            "gst_number": "24AFJPB3338N1ZF",
        })

        self.assertEqual(details["address_lines"], [
            "12 Main Road",
            "Building B",
            "Near the station",
            "Ahmedabad, State: Gujarat, Pincode: 380001",
        ])
        self.assertEqual(details["address"], "\n".join(details["address_lines"]))
        self.assertEqual(details["mobile"], "9876543210")
        self.assertEqual(details["email"], "customer@example.com")

    def test_address_keeps_first_line_next_to_label_and_compacts_location(self):
        details = app._format_customer_invoice_details({
            "address_line_1": "Survey No. 1030/164, Platinum Industrial Park",
            "address_line_2": "Vatva Railway Station Road",
            "city_village_district": "Vatva, Ahmedabad",
            "state": "Gujarat",
            "pincode": "382440",
            "customer_id": "customer-3",
            "customer_type": "business",
            "name": "Customer",
            "gst_number": "24AVQPS7090F1Z2",
        })

        self.assertEqual(details["address_lines"], [
            "Survey No. 1030/164, Platinum Industrial Park",
            "Vatva Railway Station Road",
            "Vatva, Ahmedabad, State: Gujarat, Pincode: 382440",
        ])

    def test_strips_labels_already_saved_in_address_fields(self):
        details = app._format_customer_invoice_details({
            "address_line_1": "Survey No. 1030/164, Platinum Industrial Park",
            "address_line_2": "Vatva Railway Station Road",
            "city_village_district": "City/Village/District: Vatva, Ahmedabad",
            "state": "State: Gujarat",
            "pincode": "Pincode: 382440",
            "customer_id": "customer-4",
            "customer_type": "business",
            "name": "Customer",
            "gst_number": "24AVQPS7090F1Z2",
        })

        self.assertEqual(details["address_lines"], [
            "Survey No. 1030/164, Platinum Industrial Park",
            "Vatva Railway Station Road",
            "Vatva, Ahmedabad, State: Gujarat, Pincode: 382440",
        ])

    def test_empty_split_address_remains_empty(self):
        details = app._format_customer_invoice_details({
            "address_line_1": None,
            "address_line_2": None,
            "mobile": None,
            "email": None,
            "customer_id": "customer-2",
            "customer_type": "retail",
            "name": "Retail Customer",
            "gst_number": None,
        })

        self.assertEqual(details["address_lines"], [])
        self.assertEqual(details["address"], "")
        self.assertEqual(details["mobile"], "")
        self.assertEqual(details["email"], "")
        self.assertEqual(details["gst_number"], "")

    def test_na_contact_values_are_blank_without_affecting_other_contact(self):
        details = app._format_customer_invoice_details({
            "mobile": " N/A ",
            "email": "customer@example.com",
            "customer_id": "customer-5",
            "customer_type": "retail",
            "name": "Retail Customer",
            "gst_number": None,
        })

        self.assertEqual(details["mobile"], "")
        self.assertEqual(details["email"], "customer@example.com")

    def test_invoice_bill_keeps_both_contact_labels_when_one_value_is_blank(self):
        context = {
            "item_pages": [[]],
            "Address_lines": [],
            "Address": "",
            "Addressmetal": "",
            "items": [],
            "tax_summary": [],
            "invoice_no": 1,
            "invoice_nometal": 1,
            "date": "18 November 2026",
            "datemetal": "18 November 2026",
            "customer_name": "Sample Customer",
            "customer_namemetal": "Sample Customer",
            "customer_type": "retail",
            "GSTno": "",
            "subtotal": 0,
            "chcharge": 0,
            "taxable_value": 0,
            "cgst": 0,
            "sgst": 0,
            "igst": 0,
            "grandtotal": 0,
            "grandtotal_words": "",
            "hsn": [],
            "item_columns": [],
            "item_column_widths": [],
            "product_types": [],
        }
        cases = (
            {"customer_mobile": "", "customer_email": "email-marker@example.test"},
            {"customer_mobile": "mobile-marker", "customer_email": ""},
        )

        with app.app.app_context():
            for template_name in ("invoiceply.html", "invoicemetal.html"):
                template = app.app.jinja_env.get_template(template_name)
                for contacts in cases:
                    with self.subTest(template=template_name, contacts=contacts):
                        rendered = template.render(**context, **contacts)
                        bill_text = re.sub(
                            r"\s+",
                            " ",
                            re.sub(r"<[^>]*>", " ", rendered),
                        )
                        self.assertIn("Mobile:", bill_text)
                        self.assertIn("Email:", bill_text)
                        for field, value in contacts.items():
                            marker = "mobile-marker" if field == "customer_mobile" else "email-marker@example.test"
                            if value:
                                self.assertIn(marker, bill_text)
                            else:
                                self.assertNotIn(marker, bill_text)

    def test_retail_invoice_stores_no_gst_number(self):
        payload = app._invoice_record_payload(1, {
            "customer_id": "00000000-0000-0000-0000-000000000001",
            "GSTno": "",
            "raw_date": "2026-10-31",
            "hsn": [],
            "taxable_value": 100,
            "tax": 9,
            "grandtotal": 118,
        })

        self.assertEqual(payload["customer_id"], "00000000-0000-0000-0000-000000000001")
        self.assertIsNone(payload["gst_number"])

    def test_retail_customer_can_be_created_without_gstin(self):
        customer_table = Mock()
        customer_table.insert.return_value.execute.return_value = None

        with (
            patch.dict(app.USERS, {"admin": "test"}),
            patch.dict(app.app.config, {"WTF_CSRF_ENABLED": False}),
            patch.object(app, "connection") as connection,
            app.app.test_client() as client,
        ):
            connection.return_value.table.return_value = customer_table
            with client.session_transaction() as session:
                session["_user_id"] = "admin"
                session["_fresh"] = True

            response = client.post("/add", data={
                "name": "Walk-in Customer",
                "customer_type": "retail",
                "address_line_1": "12 Main Road",
                "city_village_district": "Ahmedabad",
                "state": "Gujarat",
                "pincode": "380001",
                "mobile": "",
                "email": "",
            })

        self.assertEqual(response.status_code, 302)
        payload = customer_table.insert.call_args.args[0]
        self.assertEqual(payload["customer_type"], "retail")
        self.assertIsNone(payload["gst_number"])
        self.assertNotIn("gst", payload)

    def test_invoice_templates_compile_with_customer_detail_fields(self):
        for template_name in ("invoiceply.html", "invoicemetal.html"):
            with self.subTest(template=template_name):
                app.app.jinja_env.get_template(template_name)

    def test_vehicle_number_is_uppercase_in_invoice_context(self):
        context = self.generate_ply_invoice(
            [["laminates", "Board", "1234", "", "", "", "1", "Nos", "10"]],
            {"vehicle_number": "gj 01 ab 1234", "transport_mode": "Road"},
        )

        self.assertEqual(context["vehicle_number"], "GJ 01 AB 1234")
        self.assertEqual(context["transport_mode"], "Road")

    def test_laminates_use_nos_and_default_tax_rates(self):
        context = self.generate_ply_invoice([
            ["laminates", "Laminate sheet", "", "", "", "", "2", "Nos", "50"],
        ])

        self.assertEqual(context["items"][0]["amt"], 100)
        self.assertEqual(context["items"][0]["hsn"], "3921")
        self.assertEqual(context["cgst"], 9)
        self.assertEqual(context["sgst"], 9)
        self.assertEqual(context["igst"], 0)
        self.assertEqual(context["grandtotal"], 118)
        self.assertEqual(context["tax_summary"][0]["hsn"], "3921")
        self.assertEqual(len(context["item_pages"][0][0]["table_cells"]), 10)
        self.assertEqual(context["item_pages"][0][0]["table_cells"][1], "Laminate")

    def test_timber_cubic_feet_converts_thickness_inches(self):
        context = self.generate_ply_invoice([
            ["timber", "Timber beam", "4407", "6", "2", "3", "4", "", "100"],
        ])

        item = context["items"][0]
        self.assertEqual(item["area"], 12)
        self.assertEqual(item["unit"], "CFT")
        self.assertEqual(item["amt"], 1200)

    def test_sheet_products_use_plywood_calculations_and_suggested_hsn(self):
        context = self.generate_ply_invoice([
            ["mdf", "MDF board", "", "2", "1", "", "3", "", "10"],
            ["block_board", "Block board", "", "2", "1", "", "3", "", "10"],
            ["flushdoor", "Flush door", "", "2", "1", "", "3", "", "10"],
        ])

        self.assertEqual(
            [item["hsn"] for item in context["items"]],
            ["4411", "4412", "4418"],
        )
        for item in context["items"]:
            self.assertAlmostEqual(item["amt"], 60, places=2)
        self.assertTrue(all(item["unit"] == "sq.mtr" for item in context["items"]))
        self.assertTrue(all(item["table_cells"][5] == "3" for item in context["item_pages"][0]))

    def test_hardware_and_adhesives_support_nos_pack_and_kg(self):
        context = self.generate_ply_invoice([
            ["hardware", "Hinge", "", "", "", "", "2", "Nos", "10"],
            ["hardware", "Screws", "", "", "", "", "2", "Pack", "10"],
            ["hardware", "Nails", "", "", "", "", "2", "Kg", "10"],
            ["adhesives", "Glue pack", "", "", "", "", "2", "Pack", "10"],
            ["adhesives", "Glue kg", "", "", "", "", "2", "Kg", "10"],
        ])

        self.assertEqual(
            [item["unit"] for item in context["items"]],
            ["Nos", "Pack", "Kg", "Pack", "Kg"],
        )
        self.assertEqual(
            [item["hsn"] for item in context["items"]],
            ["8302", "8302", "7318", "3506", "3506"],
        )
        self.assertEqual([item["amt"] for item in context["items"]], [20] * 5)

    def test_plywood_keeps_square_foot_pricing(self):
        context = self.generate_ply_invoice([
            ["plywood", "Plywood sheet", "4412", "2", "1", "", "3", "", "10"],
        ])

        self.assertEqual(context["items"][0]["area"], 0.557)
        self.assertAlmostEqual(context["items"][0]["amt"], 60, places=2)
        self.assertEqual(context["item_pages"][0][0]["table_cells"][6], "0.557")
        self.assertEqual(context["item_pages"][0][0]["table_cells"][3], "0.61 m x 0.30 m")
        self.assertEqual(context["item_pages"][0][0]["table_cells"][7], "SQM")
        self.assertEqual(context["item_pages"][0][0]["table_cells"][5], "3")
        self.assertEqual(context["item_pages"][0][0]["table_cells"][8], "107.64 / SQM")

    def test_plywood_uses_standard_metric_lengths_and_converts_sqft_rate(self):
        context = self.generate_ply_invoice([
            ["plywood", "Standard size", "4412", "8", "6", "", "1", "", "10"],
            ["plywood", "Standard size", "4412", "7", "4", "", "1", "", "10"],
            ["plywood", "Standard size", "4412", "3", "2", "", "1", "", "10"],
        ])

        self.assertEqual(
            [item["dimensions"] for item in context["items"]],
            ["2.44 m x 1.84 m", "2.14 m x 1.22 m", "0.92 m x 0.61 m"],
        )
        expected_amounts = [
                2.44 * 1.84 * 10 * 10.764,
                2.14 * 1.22 * 10 * 10.764,
                0.92 * 2 * 0.3048 * 10 * 10.764,
        ]
        for item, expected_amount in zip(context["items"], expected_amounts):
            self.assertAlmostEqual(item["amt"], expected_amount)
        self.assertEqual(
            [item["table_cells"][3] for item in context["items"]],
            ["2.44 m x 1.84 m", "2.14 m x 1.22 m", "0.92 m x 0.61 m"],
        )

    def test_other_sheet_sizes_use_standard_feet_to_meters_conversion(self):
        context = self.generate_ply_invoice([
            ["plywood", "Non-standard size", "4412", "5", "2", "", "1", "", "10"],
        ])

        self.assertEqual(context["items"][0]["dimensions"], "1.52 m x 0.61 m")
        self.assertAlmostEqual(
            context["items"][0]["amt"],
            5 * 0.3048 * 2 * 0.3048 * 10 * 10.764,
        )

    def test_item_amount_is_not_rounded_up_and_grand_total_ceil_rounds(self):
        context = self.generate_ply_invoice([
            ["laminates", "Laminate sheet", "", "", "", "", "1", "Nos", "9.4", "0", "0", "0"],
        ])

        self.assertEqual(context["items"][0]["amt"], 9.4)
        self.assertEqual(context["grandtotal"], 10)

    def test_item_amount_displays_three_decimal_places_without_changing_calculation(self):
        context = self.generate_ply_invoice([
            ["plywood", "Precise amount", "", "2", "1", "", "1", "", "10"],
        ])

        item = context["items"][0]
        self.assertAlmostEqual(
            item["amt"],
            2 * 0.3048 * 0.3048 * 10 * 10.764,
        )
        self.assertEqual(item["table_cells"][-1], "20.000")

    def test_large_item_amount_is_rendered_without_scientific_notation(self):
        context = self.generate_ply_invoice([
            ["laminates", "Laminate sheet", "", "", "", "", "1", "Nos", "1125000"],
        ])

        self.assertEqual(context["item_pages"][0][0]["table_cells"][-1], "1125000.000")

    def test_hardware_pack_and_kilogram_calculations(self):
        context = self.generate_ply_invoice([
            ["hardware_unit", "Screws", "7318", "", "", "", "3", "Pack", "20"],
            ["hardware_kg", "Nails", "7317", "", "", "", "2.5", "Kg", "100"],
        ])

        self.assertEqual(context["items"][0]["unit"], "Pack")
        self.assertEqual(context["items"][0]["amt"], 60)
        self.assertEqual(context["items"][1]["unit"], "Kg")
        self.assertEqual(context["items"][1]["amt"], 250)
        self.assertEqual(context["item_pages"][0][0]["table_cells"][7], "PAC")
        self.assertEqual(context["item_pages"][0][1]["table_cells"][7], "KGS")

    def test_each_product_type_gets_an_editable_default_hsn_heading(self):
        context = self.generate_ply_invoice([
            ["plywood", "Plywood", "", "2", "1", "", "1", "", "10"],
            ["laminates", "Laminate", "", "", "", "", "1", "Nos", "10"],
            ["hardware_unit", "Furniture hinge", "", "", "", "", "1", "Nos", "10"],
            ["hardware_kg", "Steel fastener", "", "", "", "", "1", "Kg", "10"],
            ["timber", "Sawn timber", "", "6", "2", "3", "1", "", "10"],
        ])

        self.assertEqual(
            [item["hsn"] for item in context["items"]],
            ["4412", "3921", "8302", "7318", "4407"],
        )
        self.assertEqual(len(context["item_pages"][0]), 5)

    def test_mixed_products_are_summarized_by_hsn_and_tax_rate(self):
        context = self.generate_ply_invoice(
            [
                ["laminates", "Laminate sheet", "3921", "", "", "", "2", "Nos", "50", "2.5", "2.5", "5"],
                ["timber", "Timber beam", "4407", "6", "2", "3", "4", "", "100", "9", "9", "0"],
            ],
        )

        self.assertEqual(context["product_types"], ["laminates", "timber"])
        self.assertEqual(len(context["tax_summary"]), 2)
        self.assertEqual(context["cgst"], 110.5)
        self.assertEqual(context["sgst"], 110.5)
        self.assertEqual(context["igst"], 5)
        self.assertEqual(context["grandtotal"], 1526)
        self.assertEqual(
            [item["type"] for item in context["item_pages"][0]],
            ["laminates", "timber"],
        )

    def test_same_hsn_with_different_rates_gets_separate_tax_rows(self):
        context = self.generate_ply_invoice([
            ["laminates", "Sheet A", "3921", "", "", "", "1", "Nos", "100", "9", "9", "0"],
            ["laminates", "Sheet B", "3921", "", "", "", "1", "Nos", "100", "0", "0", "18"],
        ])

        self.assertEqual(len(context["tax_summary"]), 2)
        self.assertEqual(
            [(row["hsn"], row["cgst_rate"], row["igst_rate"]) for row in context["tax_summary"]],
            [("3921", 9, 0), ("3921", 0, 18)],
        )
        self.assertEqual(context["cgst"], 9)
        self.assertEqual(context["sgst"], 9)
        self.assertEqual(context["igst"], 18)

    def test_carting_and_handling_has_fixed_eighteen_percent_tax(self):
        context = self.generate_ply_invoice(
            [["laminates", "Laminate sheet", "", "", "", "", "1", "Nos", "100"]],
            {"chcharge": "100"},
        )

        carting_row = next(
            row for row in context["tax_summary"] if row["hsn"] == "Carting & Handling"
        )
        self.assertEqual(
            (carting_row["cgst_rate"], carting_row["sgst_rate"], carting_row["igst_rate"]),
            (9, 9, 0),
        )
        self.assertEqual((carting_row["cgst"], carting_row["sgst"]), (9, 9))

    def test_ply_invoice_renders_dynamic_columns_and_hsn_tax_breakdown(self):
        context = self.generate_ply_invoice(
            [
                ["laminates", "Laminate sheet", "3921", "", "", "", "2", "Nos", "50", "2.5", "2.5", "5"],
                ["timber", "Timber beam", "4407", "6", "2", "3", "4", "", "100", "9", "9", "0"],
                ["hardware_unit", "Furniture hinge", "8302", "", "", "", "1", "Nos", "25"],
                ["hardware_kg", "Steel fastener", "7318", "", "", "", "1", "Kg", "10"],
                ["plywood", "Plywood sheet", "4412", "2", "1", "", "1", "", "10"],
            ],
        )

        with app.app.test_request_context("/preview"):
            rendered = app.render_template("invoiceply.html", **context)

        self.assertIn("HSN Code", rendered)
        self.assertIn('<th colspan="2">CGST</th>', rendered)
        self.assertIn('<th colspan="2">SGST</th>', rendered)
        self.assertIn('<th colspan="2">IGST</th>', rendered)
        self.assertEqual(rendered.count("<th>Rate (%)</th>"), 3)
        self.assertIn('<td class="tax-rate">2.50%</td>', rendered)
        self.assertIn('<td class="tax-rate">5.00%</td>', rendered)
        self.assertIn("<td>100.00</td>", rendered)
        self.assertIn("Laminate sheet", rendered)
        self.assertIn("Timber beam", rendered)
        self.assertEqual(rendered.count('<table class="items">'), 1)
        self.assertEqual(rendered.count("<thead>"), 2)
        self.assertNotIn("<caption>", rendered)
        self.assertIn("Sr. No.", rendered)
        self.assertIn("Product Type", rendered)
        self.assertIn("Unit Quantity Code (UQC)", rendered)
        self.assertIn("Description", rendered)
        self.assertNotIn("IRN", rendered)
        self.assertEqual(rendered.count('<td class="description">'), 5)
        self.assertEqual(rendered.count('<tr class="items-data-row">'), 5)
        self.assertIn('<tr class="items-fill-row" aria-hidden="true">', rendered)
        self.assertIn(".items .items-data-row { height: 1px; }", rendered)
        self.assertIn(".items .items-fill-row { height: 100%; }", rendered)
        self.assertEqual(context["item_pages"][0][1]["table_cells"][3], "6 ft x 2 ft x 3 in")
        self.assertEqual(context["item_pages"][0][0]["table_cells"][8], "50 / NOS")
        self.assertEqual(context["item_pages"][0][1]["table_cells"][6], "0.339802")
        self.assertEqual(context["item_pages"][0][1]["table_cells"][7], "CBM")
        self.assertEqual(context["item_pages"][0][1]["table_cells"][8], "3531.47 / CBM")
        self.assertEqual(context["item_pages"][0][0]["table_cells"][7], "NOS")
        self.assertEqual(context["item_pages"][0][0]["table_cells"][5], "-")
        self.assertEqual(context["item_pages"][0][2]["table_cells"][7], "NOS")
        self.assertEqual(context["item_pages"][0][3]["table_cells"][7], "KGS")
        self.assertEqual(context["item_pages"][0][4]["table_cells"][7], "SQM")
        self.assertEqual(sum(app.PLY_ITEM_COLUMN_WIDTHS), 100)
        self.assertIn(".items { flex: 1; min-height: 0;", rendered)
        self.assertIn("border: 1px solid #555", rendered)
        self.assertIn("border-left: 1px solid #999; border-right: 1px solid #999", rendered)

    def test_invoice_record_stores_igst_amount(self):
        payload = app._invoice_record_payload(1, {
            "customer_id": "00000000-0000-0000-0000-000000000001",
            "GSTno": "24AVQPS7090F1Z2",
            "raw_date": "2026-11-01",
            "hsn": ["3920"],
            "taxable_value": 100,
            "cgst": 2.5,
            "sgst": 2.5,
            "igst": 5,
            "grandtotal": 110,
        })

        self.assertEqual(payload["igst"], 5)


if __name__ == "__main__":
    unittest.main()
