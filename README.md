# 🧾 Shreeji Sales Corporation – Invoice Generator

This repository contains the codebase for the internal invoice management system used by **Shreeji Sales Corporation**, designed to simplify and digitize the invoicing workflow.

The tool performs automatic calculations, handles unit conversions, generates professional PDF invoices, and securely stores them in Google Drive.

---

## 🛠️ Tech Stack

- **Backend**: Python (Flask)
- **Frontend**: HTML, CSS, JavaScript (Jinja templates)
- **Database**: Supabase (PostgreSQL)
- **PDF Generation**: PDFBolt API
- **Cloud Storage**: Google Drive API

---

## 🚀 Features

- 🧾 Dynamic Invoice Creation
- 📐 Auto-calculation and unit conversion (mm ⇄ inch, sq.ft ⇄ sq.m, etc.)
- 📄 HTML-to-PDF conversion using PDFBolt
- ☁️ Auto-upload invoices to Google Drive
- 🗃️ Supabase integration for real-time data storage and retrieval
- 🔐 Secure with CSRF protection and minimal Flask security best practices

---

## Customer records and retail invoices

Customer records use a stable `customer_id` rather than GSTIN as their identifier.
Each record is classified as `business` or `retail` and stores address lines,
area/landmark, city/district, state, pincode, mobile number, and email separately.
GSTIN is required and unique for business customers; retail customers have a
NULL GSTIN and can still be selected for either invoice type. Retail invoices
are labelled **RETAIL INVOICE** and show **RETAIL** instead of a GSTIN.

Ply invoices support plywood, MDF, block board, flushdoor, laminate, hardware,
adhesives, and timber calculations. Sheet products use plywood calculations;
hardware and adhesives support Nos, Pack, or Kg units. Each item has its own
CGST, SGST, and IGST rates (default 9%, 9%, and 0%). The tax breakdown groups
items by HSN and rate, showing separate rows when the same HSN has different
rates. Carting and handling is taxed at 18% total (9% CGST and 9% SGST).
Suggested HSN codes are editable and should be checked against the exact goods
being sold, since material and construction can change classification.

Apply all SQL migrations in `supabase/migrations` before deploying the updated
application. They backfill existing customer and invoice references, remove old
customer columns, and add IGST storage to invoice records.

## Render deployment

Render starts the application with the root `Procfile` using Gunicorn. Set the
environment variables listed in `.env.example` in the Render dashboard; do not
commit `.env`, service-account keys, or customer data. `/healthz` is a
dependency-independent health check and can be configured as the Render health
check path.

Set `FLASK_USERS_JSON` to a JSON object mapping usernames to Werkzeug password
hashes; the empty example value does not create a login account.

For Google Drive, configure either `GOOGLE_SERVICE_ACCOUNT_JSON` (or
`GOOGLE_SERVICE_ACCOUNT_JSON_BASE64`) or the OAuth variables shown in
`.env.example`. The service account must have access to the invoice and
statement folders. Rotate any credentials that have previously been committed.

For local development, copy `.env.example` to `.env`, set local values, and run
`python app.py`. The development server is bound to localhost; use `APP_PORT` to
choose its port. Production debug mode is disabled.

---

## 📂 Usage

> This tool is intended for internal use by Shreeji Sales Corporation. Please contact the repository maintainer for demo access or deployment queries.

---

## 👨‍💻 Developed By

This invoice system was developed by [Priyan Bhatt](https://github.com/priyanbhatt), in collaboration with Shreeji Sales Corporation.

---

For support or feature requests:
📧 **shreejisalescorp@gmail.com**
