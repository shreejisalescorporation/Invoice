import os
import unittest
from unittest.mock import call, patch

from googleapiclient.errors import HttpError
from httplib2 import Response

os.environ.setdefault("FLASK_SECRET_KEY", "test-session-secret")
os.environ.setdefault("WTF_CSRF_SECRET_KEY", "test-csrf-secret")
os.environ.setdefault("FLASK_USERS_JSON", "{}")

from postgrest.exceptions import APIError

import app


def duplicate_invoice_error():
    return APIError({
        "code": "23505",
        "details": "Key already exists",
        "hint": None,
        "message": "duplicate key value violates unique constraint",
    })


def invoice_context():
    return {
        "customer_id": "00000000-0000-0000-0000-000000000001",
        "GSTno": "GST123",
        "raw_date": "2026-10-31",
        "taxable_value": 100.0,
        "tax": 9.0,
        "grandtotal": 118,
        "hsn": [44123190],
        "customer_name": "Customer",
        "date": "31 October 2026",
    }


class InvoiceWorkflowTests(unittest.TestCase):
    def test_drive_upload_supports_shared_drives(self):
        service = unittest.mock.Mock()
        service.files.return_value.create.return_value.execute.return_value = {
            "id": "drive-file-1",
            "webViewLink": "https://drive.example/file-1",
        }
        with (
            patch.object(app, "INVOICE_FOLDER_ID", "shared-folder"),
            patch.object(app, "get_drive_service", return_value=service),
        ):
            result = app.upload_pdf(b"%PDF-1.7", "invoice.pdf", "invoice")

        self.assertEqual(result, ("drive-file-1", "https://drive.example/file-1"))
        kwargs = service.files.return_value.create.call_args.kwargs
        self.assertEqual(kwargs["body"]["parents"], ["shared-folder"])
        self.assertTrue(kwargs["supportsAllDrives"])
        self.assertEqual(kwargs["media_body"].mimetype(), "application/pdf")

    def test_drive_storage_quota_error_explains_required_configuration(self):
        service = unittest.mock.Mock()
        quota_error = HttpError(
            Response({"status": "403", "reason": "Forbidden"}),
            b'{"error":{"errors":[{"reason":"storageQuotaExceeded"}]}}',
            uri="https://www.googleapis.com/upload/drive/v3/files",
        )
        service.files.return_value.create.return_value.execute.side_effect = quota_error
        with (
            patch.object(app, "INVOICE_FOLDER_ID", "my-drive-folder"),
            patch.object(app, "get_drive_service", return_value=service),
        ):
            with self.assertRaisesRegex(
                app.DriveStorageQuotaError,
                "Shared Drive",
            ):
                app.upload_pdf(b"%PDF-1.7", "invoice.pdf", "invoice")

    def test_shared_drive_cleanup_sets_supports_all_drives(self):
        service = unittest.mock.Mock()
        with patch.object(app, "get_drive_service", return_value=service):
            app.delete_uploaded_pdf("drive-file-1")

        service.files.return_value.delete.assert_called_once_with(
            fileId="drive-file-1",
            supportsAllDrives=True,
        )

    def test_ply_pdf_request_uses_pdfbolt_supported_options(self):
        with (
            patch.object(app, "render_template", return_value="<html></html>"),
            patch.object(app, "_request_pdf", return_value=b"%PDF-1.7") as request_pdf,
        ):
            pdf = app.create_pdf({}, form_type="Ply")

        self.assertEqual(pdf, b"%PDF-1.7")
        request_pdf.assert_called_once()
        self.assertEqual(request_pdf.call_args.args, ("<html></html>",))
        options = request_pdf.call_args.kwargs
        self.assertEqual(options["format"], "A4")
        self.assertTrue(options["printBackground"])
        self.assertEqual(options["emulateMediaType"], "print")
        self.assertNotIn("preferCSSPageSize", options)

    def test_drive_service_uses_service_account_json_from_environment(self):
        credentials = object()
        with (
            patch.dict(
                os.environ,
                {
                    "GOOGLE_SERVICE_ACCOUNT_JSON": '{"type":"service_account"}',
                    "GOOGLE_CLIENT_ID": "",
                    "GOOGLE_CLIENT_SECRET": "",
                    "GOOGLE_REFRESH_TOKEN": "",
                    "GOOGLE_OAUTH_CLIENT_JSON": "",
                },
            ),
            patch.object(
                app.service_account.Credentials,
                "from_service_account_info",
                return_value=credentials,
            ) as load_credentials,
            patch.object(app, "build", return_value="drive-service") as build_service,
        ):
            result = app.get_drive_service()

        self.assertEqual(result, "drive-service")
        load_credentials.assert_called_once_with(
            {"type": "service_account"},
            scopes=app.SCOPES,
        )
        build_service.assert_called_once_with(
            "drive",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )

    def test_oauth_credentials_take_precedence_over_service_account(self):
        credentials = unittest.mock.Mock()
        with (
            patch.dict(
                os.environ,
                {
                    "GOOGLE_CLIENT_ID": "oauth-client-id",
                    "GOOGLE_CLIENT_SECRET": "oauth-client-secret",
                    "GOOGLE_REFRESH_TOKEN": "oauth-refresh-token",
                    "GOOGLE_SERVICE_ACCOUNT_JSON": '{"type":"service_account"}',
                },
            ),
            patch.object(app, "Credentials", return_value=credentials) as create_credentials,
            patch.object(app, "GoogleAuthRequest") as auth_request,
            patch.object(app, "_service_account_credentials") as service_account_credentials,
            patch.object(app, "build", return_value="drive-service") as build_service,
        ):
            result = app.get_drive_service()

        self.assertEqual(result, "drive-service")
        create_credentials.assert_called_once_with(
            token=None,
            refresh_token="oauth-refresh-token",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="oauth-client-id",
            client_secret="oauth-client-secret",
            scopes=app.SCOPES,
        )
        credentials.refresh.assert_called_once_with(auth_request.return_value)
        service_account_credentials.assert_not_called()
        build_service.assert_called_once_with(
            "drive",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )

    def test_oauth_client_json_can_supply_client_id_and_secret(self):
        credentials = unittest.mock.Mock()
        with (
            patch.dict(
                os.environ,
                {
                    "GOOGLE_CLIENT_ID": "",
                    "GOOGLE_CLIENT_SECRET": "",
                    "GOOGLE_REFRESH_TOKEN": "oauth-refresh-token",
                    "GOOGLE_OAUTH_CLIENT_JSON": (
                        '{"web":{"client_id":"json-client-id",'
                        '"client_secret":"json-client-secret"}}'
                    ),
                },
            ),
            patch.object(app, "Credentials", return_value=credentials) as create_credentials,
            patch.object(app, "GoogleAuthRequest"),
        ):
            result = app._oauth_credentials()

        self.assertIs(result, credentials)
        create_credentials.assert_called_once_with(
            token=None,
            refresh_token="oauth-refresh-token",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="json-client-id",
            client_secret="json-client-secret",
            scopes=app.SCOPES,
        )

    def test_incomplete_oauth_configuration_fails_instead_of_using_service_account(self):
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "oauth-client-id",
                "GOOGLE_CLIENT_SECRET": "",
                "GOOGLE_REFRESH_TOKEN": "",
                "GOOGLE_SERVICE_ACCOUNT_JSON": '{"type":"service_account"}',
                "GOOGLE_OAUTH_CLIENT_JSON": "",
            },
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN",
            ):
                app.get_drive_service()

    def test_pdfbolt_http_error_includes_provider_error_details(self):
        response = unittest.mock.Mock()
        response.status_code = 400
        response.json.return_value = {
            "errorCode": "BAD_REQUEST",
            "errorMessage": "Invalid conversion parameter",
        }
        response.raise_for_status.side_effect = app.requests.HTTPError("400 Client Error")

        with (
            patch.dict(os.environ, {"PDFBOLT_API_KEY": "test-key"}),
            patch.object(app.requests, "post", return_value=response),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "PDFBolt rejected the PDF request \\(HTTP 400\\): "
                "BAD_REQUEST; Invalid conversion parameter",
            ):
                app._request_pdf("<html></html>", format="A4")

    def test_primary_key_collision_removes_orphan_and_retries_with_new_number(self):
        context = invoice_context()
        created_invoice_numbers = []

        def create_pdf(invoice_context, form_type):
            created_invoice_numbers.append(
                (invoice_context["invoice_no"], form_type)
            )
            return b"%PDF-1.7 document"

        with (
            patch.object(
                app,
                "get_next_invoice_number_and_address",
                side_effect=[(7, "Address"), (8, "Address")],
            ),
            patch.object(app, "create_pdf", side_effect=create_pdf),
            patch.object(
                app,
                "_upload_pdf_content",
                side_effect=[("file-7", None), ("file-8", None)],
            ),
            patch.object(
                app,
                "save_invoice_record",
                side_effect=[duplicate_invoice_error(), None],
            ) as save_record,
            patch.object(app, "delete_uploaded_pdf") as delete_pdf,
        ):
            invoice_no, filename = app.create_and_store_invoice(context, "Ply")

        self.assertEqual(invoice_no, 8)
        self.assertEqual(filename, "8-Customer-31October2026.pdf")
        self.assertEqual(
            [entry.args[0]["invoice_no"] for entry in save_record.call_args_list],
            [7, 8],
        )
        self.assertEqual(delete_pdf.call_args_list, [call("file-7")])
        self.assertEqual(created_invoice_numbers, [(7, "Ply"), (8, "Ply")])

    def test_database_failure_removes_drive_pdf_when_no_record_was_saved(self):
        with (
            patch.object(app, "get_next_invoice_number_and_address", return_value=(7, "Address")),
            patch.object(app, "create_pdf", return_value=b"%PDF-1.7 document"),
            patch.object(app, "_upload_pdf_content", return_value=("file-7", None)),
            patch.object(app, "save_invoice_record", side_effect=RuntimeError("database offline")),
            patch.object(app, "invoice_record_matches", return_value=False),
            patch.object(app, "delete_uploaded_pdf") as delete_pdf,
        ):
            with self.assertRaisesRegex(app.InvoiceProcessingError, "PDF was removed"):
                app.create_and_store_invoice(invoice_context(), "Ply")

        delete_pdf.assert_called_once_with("file-7")

    def test_ambiguous_database_response_is_verified_without_deleting_document(self):
        with (
            patch.object(app, "get_next_invoice_number_and_address", return_value=(7, "Address")),
            patch.object(app, "create_pdf", return_value=b"%PDF-1.7 document"),
            patch.object(app, "_upload_pdf_content", return_value=("file-7", None)),
            patch.object(app, "save_invoice_record", side_effect=RuntimeError("response lost")),
            patch.object(app, "invoice_record_matches", return_value=True),
            patch.object(app, "delete_uploaded_pdf") as delete_pdf,
        ):
            invoice_no, filename = app.create_and_store_invoice(invoice_context(), "Ply")

        self.assertEqual(invoice_no, 7)
        self.assertEqual(filename, "7-Customer-31October2026.pdf")
        delete_pdf.assert_not_called()

    def test_pdf_failure_does_not_save_an_invoice_record(self):
        with (
            patch.object(app, "get_next_invoice_number_and_address", return_value=(7, "Address")),
            patch.object(app, "create_pdf", side_effect=RuntimeError("PDF service unavailable")),
            patch.object(app, "_upload_pdf_content") as upload_pdf,
            patch.object(app, "save_invoice_record") as save_record,
        ):
            with self.assertRaisesRegex(RuntimeError, "PDF service unavailable"):
                app.create_and_store_invoice(invoice_context(), "Ply")

        upload_pdf.assert_not_called()
        save_record.assert_not_called()

    def test_drive_upload_failure_does_not_save_an_invoice_record(self):
        with (
            patch.object(app, "get_next_invoice_number_and_address", return_value=(7, "Address")),
            patch.object(app, "create_pdf", return_value=b"%PDF-1.7 document"),
            patch.object(app, "_upload_pdf_content", side_effect=RuntimeError("Drive unavailable")),
            patch.object(app, "save_invoice_record") as save_record,
        ):
            with self.assertRaisesRegex(RuntimeError, "Drive unavailable"):
                app.create_and_store_invoice(invoice_context(), "Ply")

        save_record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
