from flask import (
    Flask,
    flash,
    get_flashed_messages,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from num2words import num2words
import base64
import requests
from supabase import Client, create_client
import tempfile
import json
import os
import math
import re
import uuid
from datetime import datetime
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf
from postgrest.exceptions import APIError
from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()




SCOPES = ["https://www.googleapis.com/auth/drive.file"]  # least privilege
INVOICE_FOLDER_ID = os.getenv("INVOICE_FOLDER_ID")
STATEMENT_FOLDER_ID = os.getenv("STATEMENT_FOLDER_ID")


def get_access_token():
    credentials = {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "refresh_token": os.getenv("GOOGLE_REFRESH_TOKEN"),
    }
    missing = [name for name, value in credentials.items() if not value]
    if missing:
        raise RuntimeError(
            "Google Drive OAuth configuration is incomplete: "
            + ", ".join(missing)
        )
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={**credentials, "grant_type": "refresh_token"},
        timeout=(5, 20),
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _service_account_credentials():
    raw_credentials = (
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        or os.getenv("GOOGLE_CREDENTIALS_JSON")
    )
    encoded_credentials = (
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_BASE64")
        or os.getenv("GOOGLE_CREDENTIALS_BASE64")
    )
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if raw_credentials:
        info = json.loads(raw_credentials)
    elif encoded_credentials:
        info = json.loads(
            base64.b64decode(encoded_credentials, validate=True).decode("utf-8")
        )
    elif credentials_path and os.path.isfile(credentials_path):
        with open(credentials_path, encoding="utf-8") as credentials_file:
            info = json.load(credentials_file)
    else:
        return None

    if not isinstance(info, dict) or info.get("type") != "service_account":
        raise RuntimeError(
            "Google service-account configuration must be a service account JSON object."
        )
    return service_account.Credentials.from_service_account_info(
        info,
        scopes=SCOPES,
    )

def get_drive_service():
    creds = _service_account_credentials()
    if creds is None:
        creds = Credentials(get_access_token())
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    return service

def upload_pdf(filepath: str, filename: str, to_folder: str):
    folder_id = INVOICE_FOLDER_ID if to_folder.lower() == "invoice" else STATEMENT_FOLDER_ID
    if not folder_id:
        raise RuntimeError("Folder ID not configured in INVOICE_FOLDER_ID / STATEMENT_FOLDER_ID")

    service = get_drive_service()
    media = MediaFileUpload(filepath, mimetype="application/pdf")
    file_metadata = {"name": filename, "parents": [folder_id]}

    res = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink"
    ).execute()
    return res.get("id"), res.get("webViewLink")


def delete_uploaded_pdf(file_id: str):
    service = get_drive_service()
    service.files().delete(fileId=file_id).execute()






















































# # INVOICE_FOLDER_ID   = os.getenv("INVOICE_FOLDER_ID")
# # STATEMENT_FOLDER_ID = os.getenv("STATEMENT_FOLDER_ID")
# SERVICE_ACCOUNT_EMAIL = os.getenv("SERVICE_ACCOUNT_EMAIL")
# SCOPES = ["https://www.googleapis.com/auth/drive"]
# TOKEN_PATH = 'token.pickle'
# CREDENTIALS_PATH = 'credentials.json'

# def _load_service_account_info():
#     raw = os.getenv("GOOGLE_CREDENTIALS_JSON")
#     if raw:
#         info = json.loads(raw)
#     else:
#         b64 = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_BASE64")
#         decoded = base64.b64decode(b64)
#         info = json.loads(decoded)
#     required = ["type", "client_email", "private_key", "token_uri"]
#     missing = [k for k in required if k not in info]
#     if missing:
#         raise ValueError(f"Missing service account fields: {missing}")

#     token_b64 = os.getenv("GOOGLE_TOKEN_B64")
#     if not token_b64:
#         raise RuntimeError("Missing GOOGLE_TOKEN_B64 (base64 token.pickle)")

#     token_bytes = base64.b64decode(token_b64)
#     creds = pickle.loads(token_bytes)
#     return creds,info


# def get_drive_service():
#     """
#     Authenticates using the service account key pointed to by
#     GOOGLE_APPLICATION_CREDENTIALS and returns a Drive v3 service.
#     """
#     # creds = None
#     # # 2) Load cached credentials if they exist
#     # if os.path.exists(TOKEN_PATH):
#     #     with open(TOKEN_PATH, 'rb') as token_file:
#     #         creds = pickle.load(token_file)

#     # # 3) If there are no valid creds, run the flow
#     # if not creds or not creds.valid:
#     #     if creds and creds.expired and creds.refresh_token:
#     #         creds.refresh(Request())
#     #     else:
#     #         flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
#     #         creds = flow.run_local_server(port=8080)
#     #     # 4) Save the credentials for next time
#     #     with open(TOKEN_PATH, 'wb') as token_file:
#     #         pickle.dump(creds, token_file)

#     # # 5) Build and return the Drive service
#     # return build('drive', 'v3', credentials=creds, cache_discovery=False)

#     # creds = service_account.Credentials.from_service_account_file(
#     #     os.environ["GOOGLE_APPLICATION_CREDENTIALS"], scopes=SCOPES
#     # )
#     # return build("drive", "v3", credentials=creds, cache_discovery=False)



#     creds, client_info =_load_service_account_info() 
#         # Refresh if needed
#     if creds and creds.expired and creds.refresh_token:
#         creds.refresh(Request())
#         # NOTE: creds now has a new access_token; however we cannot update Render env automatically.
#         # If you want to capture the refreshed token.pickle, fetch and re-base64 it locally and update env var.

#     if not creds or not creds.valid:
#         raise RuntimeError("Credentials invalid. Generate token.pickle locally with offline access.")

#     # creds = service_account.Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
#     return build("drive", "v3", credentials=creds, cache_discovery=False)
# def upload_pdf(filepath: str, filename: str, to_folder: str) -> str:
#     """
#     Uploads a PDF to Drive into the specified folder.
#     Returns the fileId.
#     to_folder should be either 'invoice' or 'statement'.
#     """
#     INVOICE_FOLDER_ID   = os.getenv("INVOICE_FOLDER_ID")
#     STATEMENT_FOLDER_ID = os.getenv("STATEMENT_FOLDER_ID")

#     service = get_drive_service()
#     folder_id = INVOICE_FOLDER_ID if to_folder.lower() == 'invoice' else STATEMENT_FOLDER_ID

#     file_metadata = {
#         'name': filename,
#         'parents': [folder_id],
#     }
#     media = MediaFileUpload(filepath, mimetype='application/pdf')

#     file = service.files().create(
#         body=file_metadata,
#         media_body=media,
#         fields='id, webViewLink',
#         supportsAllDrives=True
#     ).execute()

#     return file['id'], file['webViewLink']

app = Flask(__name__)
app.config['WTF_CSRF_SECRET_KEY'] = os.getenv("WTF_CSRF_SECRET_KEY")
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY environment variable not set!")
if not app.config["WTF_CSRF_SECRET_KEY"]:
    raise RuntimeError("WTF_CSRF_SECRET_KEY environment variable not set!")
is_render = os.getenv("RENDER", "").lower() == "true" or bool(
    os.getenv("RENDER_SERVICE_ID")
)
secure_cookies = os.getenv(
    "SESSION_COOKIE_SECURE",
    "true" if is_render else "false",
).lower() == "true"
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=secure_cookies,
    SESSION_COOKIE_SAMESITE="Lax",
    REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_SECURE=secure_cookies,
    MAX_CONTENT_LENGTH=4 * 1024 * 1024,
)
if is_render:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
csrf = CSRFProtect(app)


@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf)


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.is_secure:
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
    return response


@app.route("/healthz", methods=["GET"])
def health_check():
    return {"status": "ok"}, 200


def connection():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    # password=os.getenv("pass")
    # host=os.getenv("host")
    # portnum=os.getenv("port")
    # database=os.getenv("database")
    # user=os.getenv("user")
    # return pg8000.connect(
    #     user=user,
    #     password=password,
    #     host=host,
    #     database=database,
    #     port=portnum,
    #     ssl_context=True
    # )
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL or SUPABASE_KEY environment variable not set.")
    supabase: Client = create_client(url, key)
    return supabase


def load_customers():
    supabase = connection()
    response = supabase.table("customer") \
        .select("customer_id,customer_type,name,gst_number") \
        .order("name") \
        .execute()
    return response.data or []


# def requestadd(GSTno):
#     try:
#         conn=connection()
#         cursor=conn.cursor()
#         cursor.execute("SELECT address FROM customer WHERE gst = %s", (GSTno,))
#         result = (cursor.fetchone())[0]
#         add=result.strip().replace("\n","")
#         cursor.close()
#         conn.close()
#     except Exception as e:
#         return jsonify({"status":"error","message":str(e)}),500
#     return add
def _format_customer_invoice_details(customer):
    def address_value(field, label):
        value = (customer.get(field) or "").strip()
        return re.sub(
            rf"^{re.escape(label)}\s*:\s*",
            "",
            value,
            flags=re.IGNORECASE,
        ).strip()

    address_lines = [
        (customer.get("address_line_1") or "").strip(),
        (customer.get("address_line_2") or "").strip(),
    ]
    area_landmark = address_value("area_landmark", "Area/Landmark")
    if area_landmark:
        address_lines.append(area_landmark)

    city = address_value("city_village_district", "City/Village/District")
    state = address_value("state", "State")
    pincode = address_value("pincode", "Pincode")
    location = [city] if city else []
    if state:
        location.append(f"State: {state}")
    if pincode:
        location.append(f"Pincode: {pincode}")
    if location:
        address_lines.append(", ".join(location))

    address_lines = [line for line in address_lines if line]
    return {
        "address": "\n".join(address_lines),
        "address_lines": address_lines,
        "mobile": (customer.get("mobile") or "").strip(),
        "email": (customer.get("email") or "").strip(),
        "customer_id": customer["customer_id"],
        "customer_type": customer["customer_type"],
        "name": customer["name"],
        "gst_number": (customer.get("gst_number") or "").strip(),
    }


def get_customer_invoice_details(customer_id):
    response = connection().table("customer") \
        .select(
            "customer_id,customer_type,name,gst_number,address_line_1,"
            "address_line_2,area_landmark,city_village_district,state,"
            "pincode,mobile,email"
        ) \
        .eq("customer_id", customer_id) \
        .limit(1) \
        .execute()
    if not response.data:
        raise ValueError("The selected customer could not be found.")
    return _format_customer_invoice_details(response.data[0])


def get_next_invoice_number_and_address(customer_id, context=None):
    customer_details = get_customer_invoice_details(customer_id)
    if context is not None:
        context.update(
            Address=customer_details["address"],
            Address_lines=customer_details["address_lines"],
            customer_mobile=customer_details["mobile"],
            customer_email=customer_details["email"],
            customer_id=customer_details["customer_id"],
            customer_name=customer_details["name"],
            customer_namemetal=customer_details["name"],
            customer_type=customer_details["customer_type"],
            GSTno=customer_details["gst_number"],
        )

    resp = connection().table("invoice_data") \
        .select("invoice_no") \
        .order("invoice_no", desc=True) \
        .limit(1) \
        .execute()
    last_invoice = resp.data[0]["invoice_no"] if resp.data else 0
    return last_invoice + 1, customer_details["address"]


def _invoice_record_payload(invoice_no, context):
    return {
        "invoice_no": invoice_no,
        "customer_id": context["customer_id"],
        "gst_number": context["GSTno"] or None,
        "date": context["raw_date"],
        "hsn": context["hsn"],
        "total_taxable_value": context["taxable_value"],
        "cgst": context.get("cgst", context.get("tax", 0)),
        "sgst": context.get("sgst", context.get("tax", 0)),
        "igst": context.get("igst", 0),
        "grand_total": context["grandtotal"]
    }


def save_invoice_record(payload):
    connection().table("invoice_data").insert(payload).execute()


def invoice_record_matches(invoice_no, payload):
    response = connection().table("invoice_data") \
        .select(
            "invoice_no, customer_id, gst_number, date, total_taxable_value, "
            "cgst, sgst, igst, grand_total, hsn"
        ) \
        .eq("invoice_no", invoice_no) \
        .limit(1) \
        .execute()
    if not response.data:
        return False
    record = response.data[0]
    return all(record.get(key) == value for key, value in payload.items())


def _is_invoice_number_conflict(error):
    return isinstance(error, APIError) and error.code == "23505"


# Flask-Login setup

USERS = json.loads(os.getenv("FLASK_USERS_JSON", "{}"))
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


class User(UserMixin):

    def __init__(self, id):
        self.id = id


@login_manager.user_loader
def load_user(user_id):
    if user_id in USERS:
        return User(user_id)
    return None


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hash = USERS.get(username)
        if hash and check_password_hash(hash, password):
            get_flashed_messages(with_categories=True)
            user = User(username)
            login_user(user)
            return redirect(url_for('invoice_form'))
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/', methods=['GET'])
@login_required
def invoice_form():
    customers = load_customers()
    return render_template('invoice_form.html', customers=customers)


@app.route("/analysis", methods=["GET", "POST"])
@login_required
def analytics():
    customers = load_customers()
    return render_template("analytics.html", customers=customers)


def _form_value(name):
    value = request.form.get(name, "").strip()
    if not value:
        raise ValueError(f"{name.replace('_', ' ').capitalize()} is required.")
    return value


def _form_number(value, label, minimum=0):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a valid number.") from exc
    if not math.isfinite(number) or number < minimum:
        qualifier = "greater than zero" if minimum > 0 else "zero or greater"
        raise ValueError(f"{label} must be {qualifier}.")
    return number


def _form_date(name):
    value = _form_value(name)
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("Enter a valid invoice date.") from exc


def _form_customer(name):
    value = _form_value(name)
    try:
        return str(uuid.UUID(value))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Select a valid customer.") from exc


def _form_items(name, expected_fields):
    submitted_items = request.form.getlist(name)
    if not submitted_items:
        raise ValueError("Add at least one invoice item.")

    items = []
    for index, serialized in enumerate(submitted_items, start=1):
        try:
            values = json.loads(serialized)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invoice item {index} is invalid.") from exc
        if not isinstance(values, list) or len(values) != expected_fields:
            raise ValueError(f"Invoice item {index} is incomplete.")
        if not isinstance(values[0], str) or not values[0].strip():
            raise ValueError(f"Invoice item {index} needs a description.")
        items.append(values)
    return items


PLY_PRODUCT_TYPES = {
    "plywood": "Plywood",
    "mdf": "MDF",
    "block_board": "Block Board",
    "flushdoor": "Flushdoor",
    "laminates": "Laminate",
    "hardware": "Hardware",
    "adhesives": "Adhesives",
    "hardware_unit": "Hardware",
    "hardware_kg": "Hardware",
    "timber": "Timber",
}

PLY_HSN_DEFAULTS = {
    "plywood": "4412",
    "mdf": "4411",
    "block_board": "4412",
    "flushdoor": "4418",
    "laminates": "3921",
    "hardware": "8302",
    "adhesives": "3506",
    "hardware_unit": "8302",
    "hardware_kg": "7318",
    "timber": "4407",
}

PLY_SHEET_TYPES = {"plywood", "mdf", "block_board", "flushdoor"}
PLY_SIMPLE_TYPES = {"laminates", "hardware", "adhesives", "hardware_unit", "hardware_kg"}
PLY_SHEET_STANDARD_LENGTHS_M = {
    3: 0.92,
    4: 1.22,
    6: 1.84,
    7: 2.14,
    8: 2.44,
}

PLY_ITEM_COLUMNS = [
    "Sr. No.", "Product Type", "Description", "Dimensions", "HSN",
    "Alt Qty (NOS)", "Quantity", "Unit Quantity Code (UQC)", "Rate", "Amount",
]
PLY_ITEM_COLUMN_WIDTHS = [5, 10, 19, 12, 7, 8, 8, 12, 9, 10]

CGST_SGST_RATES = {"0", "1.5", "2.5", "9", "20"}
IGST_RATES = {"0", "3", "5", "18", "40"}


def _tax_rate(value, name, allowed_rates):
    if not isinstance(value, str):
        raise ValueError(f"Select a valid {name.upper()} rate.")
    value = value.strip()
    if value not in allowed_rates:
        raise ValueError(f"Select a valid {name.upper()} rate.")
    return float(value)


def _ply_sheet_length_m(length_ft):
    return PLY_SHEET_STANDARD_LENGTHS_M.get(length_ft, length_ft * 0.3048)


def _ply_item_table_cells(item):
    alt_qty = item["qty"] if item["type"] in PLY_SHEET_TYPES | {"timber"} else None
    uqc_codes = {
        "sq.mtr": "SQM",
        "Nos": "NOS",
        "Pack": "PAC",
        "Kg": "KGS",
        "CFT": "CBM",
    }
    uqc_code = uqc_codes[item["unit"]]
    quantity = item["area"]
    if item["type"] in PLY_SHEET_TYPES:
        displayed_rate = item["pr"] * 10.764
    elif item["unit"] == "CFT":
        cubic_meters_per_cubic_foot = 0.028316846592
        quantity = round(
            item.get("volume_cft", item["area"]) * cubic_meters_per_cubic_foot,
            6,
        )
        displayed_rate = item["pr"] / cubic_meters_per_cubic_foot
    else:
        displayed_rate = item["pr"]
    rate = f'{displayed_rate:g} / {uqc_code}'
    dimensions = item.get("dimensions") or None
    values = [
        item["no"],
        item["type_label"],
        item["desc"],
        dimensions,
        item["hsn"],
        alt_qty,
        quantity,
        uqc_code,
        rate,
        item["amt"],
    ]
    return [
        "-" if value is None or value == "" else
        f"{value:.3f}" if index == len(values) - 1 and isinstance(value, float) else
        f"{value:f}".rstrip("0").rstrip(".") if isinstance(value, float) else value
        for index, value in enumerate(values)
    ]


def _summarize_invoice_taxes(items, chcharge):
    taxable_by_hsn_and_rates = {}
    for item in items:
        key = (
            item["hsn"],
            item["cgst_rate"],
            item["sgst_rate"],
            item["igst_rate"],
        )
        taxable_by_hsn_and_rates[key] = (
            taxable_by_hsn_and_rates.get(key, 0) + item["amt"]
        )
    if chcharge:
        key = ("Carting & Handling", 9.0, 9.0, 0.0)
        taxable_by_hsn_and_rates[key] = (
            taxable_by_hsn_and_rates.get(key, 0) + chcharge
        )

    summary = []
    for (
        hsn,
        cgst_rate,
        sgst_rate,
        igst_rate,
    ), taxable_value in taxable_by_hsn_and_rates.items():
        summary.append({
            "hsn": hsn,
            "cgst_rate": cgst_rate,
            "sgst_rate": sgst_rate,
            "igst_rate": igst_rate,
            "taxable_value": round(taxable_value, 2),
            "cgst": round(taxable_value * cgst_rate / 100, 2),
            "sgst": round(taxable_value * sgst_rate / 100, 2),
            "igst": round(taxable_value * igst_rate / 100, 2),
        })

    return {
        "summary": summary,
        "cgst": round(sum(row["cgst"] for row in summary), 2),
        "sgst": round(sum(row["sgst"] for row in summary), 2),
        "igst": round(sum(row["igst"] for row in summary), 2),
    }


def generate_invoice_metal():
    date_obj = _form_date("datemetal")
    raw_date = date_obj.strftime("%Y-%m-%d")
    date = date_obj.strftime("%d %B %Y")
    customer_id = _form_customer("customer_namemetal")
    customer_details = get_customer_invoice_details(customer_id)
    chcharge = _form_number(_form_value("chchargemetal"), "Carting and handling charges")
    items = []
    hsnlist = []
    subtotal = 0.0
    for idx, values in enumerate(_form_items("itemsmetal[]", 4), start=1):
        desc, hsn, qty_value, price_value = values
        if not isinstance(hsn, str) or not hsn.strip():
            raise ValueError(f"Invoice item {idx} needs a valid HSN code.")
        qty = _form_number(qty_value, f"Quantity for item {idx}", minimum=0.000001)
        priceperkg = _form_number(price_value, f"Price for item {idx}")
        amt = priceperkg * qty
        subtotal += amt
        hsnlist.append(hsn.strip())
        items.append({
            'no': idx,
            'desc': desc.strip(),
            'hsn': hsn.strip(),
            'qty': qty,
            'unit': 'kgs',
            'pr': round(priceperkg, 3),
            'amt': round(amt, 3)
        })

    # 3) Totals and words
    taxable_value = subtotal + chcharge
    tax = taxable_value * 0.09
    grandtotal = round(taxable_value + 2 * tax)
    grandtotal_words = (num2words(grandtotal, lang='en_IN').replace(
        ' point ', ' and ')).replace(",", "").title() + " Only"
    # 4) Render HTML
    context = {
        'invoice_nometal': "null",
        'datemetal': date,
        'customer_namemetal': customer_details["name"],
        'customer_name': customer_details["name"],
        'customer_id': customer_id,
        'customer_type': customer_details["customer_type"],
        'GSTno': customer_details["gst_number"],
        'Address_lines': customer_details["address_lines"],
        'customer_mobile': customer_details["mobile"],
        'customer_email': customer_details["email"],
        'Addressmetal': "Address",
        'items': items,
        'subtotal': round(subtotal, 3),
        'chcharge': round(chcharge, 2),
        "taxable_value": round(taxable_value, 3),
        'tax': round(tax, 3),
        'grandtotal': grandtotal,
        'grandtotal_words': grandtotal_words,
        "raw_date": raw_date,
        "hsn": hsnlist
    }

    return context


def generate_invoice():
    date_obj = _form_date("date")
    raw_date = date_obj.strftime("%Y-%m-%d")
    date = date_obj.strftime("%d %B %Y")
    customer_id = _form_customer("customer_name")
    customer_details = get_customer_invoice_details(customer_id)
    chcharge = _form_number(_form_value("chcharge"), "Carting and handling charges")
    items = []
    subtotal = 0.0
    for idx, values in enumerate(_form_items("items[]", 12), start=1):
        (
            product_type,
            desc,
            hsn,
            length_value,
            width_value,
            thickness_value,
            qty_value,
            unit_value,
            price_value,
            cgst_rate_value,
            sgst_rate_value,
            igst_rate_value,
        ) = values
        if product_type not in PLY_PRODUCT_TYPES:
            raise ValueError(f"Invoice item {idx} has an invalid product type.")
        if not isinstance(desc, str) or not desc.strip():
            raise ValueError(f"Invoice item {idx} needs a description.")
        if not isinstance(hsn, str):
            hsn = ""
        hsn = hsn.strip()
        hsn_was_provided = bool(hsn)
        if not hsn:
            hsn = PLY_HSN_DEFAULTS[product_type]
        cgst_rate = _tax_rate(cgst_rate_value, "CGST", CGST_SGST_RATES)
        sgst_rate = _tax_rate(sgst_rate_value, "SGST", CGST_SGST_RATES)
        igst_rate = _tax_rate(igst_rate_value, "IGST", IGST_RATES)

        qty = _form_number(qty_value, f"Quantity for item {idx}", minimum=0.000001)
        rate = _form_number(price_value, f"Rate for item {idx}")
        item = {
            "no": idx,
            "type": product_type,
            "type_label": PLY_PRODUCT_TYPES[product_type],
            "desc": desc.strip(),
            "hsn": hsn.strip(),
            "qty": qty,
            "cgst_rate": cgst_rate,
            "sgst_rate": sgst_rate,
            "igst_rate": igst_rate,
        }

        if product_type in PLY_SHEET_TYPES:
            length_ft = _form_number(
                length_value, f"Length for item {idx}", minimum=0.000001
            )
            width_ft = _form_number(
                width_value, f"Width for item {idx}", minimum=0.000001
            )
            length_m = _ply_sheet_length_m(length_ft)
            width_m = _ply_sheet_length_m(width_ft)
            area = length_m * width_m * qty
            rate_per_sqm = rate * 10.764
            amt = area * rate_per_sqm
            item.update(
                l=round(length_m, 2),
                b=round(width_m, 2),
                area=round(area, 3),
                unit="sq.mtr",
                pr=round(rate, 2),
                dimensions=f"{length_m:.2f} m x {width_m:.2f} m",
            )
        elif product_type in PLY_SIMPLE_TYPES:
            if product_type == "laminates":
                unit = "Nos"
            elif product_type in {"hardware", "adhesives"}:
                if unit_value not in {"Nos", "Pack", "Kg"}:
                    raise ValueError(
                        f"Select Nos, Pack, or Kg for {PLY_PRODUCT_TYPES[product_type]} item {idx}."
                    )
                unit = unit_value
                if product_type == "hardware" and unit == "Kg" and not hsn_was_provided:
                    hsn = PLY_HSN_DEFAULTS["hardware_kg"]
                    item["hsn"] = hsn
            elif product_type == "hardware_unit":
                if unit_value not in {"Nos", "Pack"}:
                    raise ValueError(f"Select Nos or Pack for hardware item {idx}.")
                unit = unit_value
            else:
                unit = "Kg"
            amt = round(qty * rate, 2)
            item.update(area=qty, unit=unit, pr=round(rate, 2), dimensions="-")
        else:
            length_ft = _form_number(
                length_value, f"Length for item {idx}", minimum=0.000001
            )
            width_ft = _form_number(
                width_value, f"Width for item {idx}", minimum=0.000001
            )
            thickness_in = _form_number(
                thickness_value, f"Thickness for item {idx}", minimum=0.000001
            )
            volume_cft = length_ft * width_ft * (thickness_in / 12) * qty
            amt = round(volume_cft * rate, 2)
            item.update(
                area=round(volume_cft, 3),
                volume_cft=volume_cft,
                unit="CFT",
                pr=round(rate, 2),
                dimensions=(
                    f"{length_ft:g} ft x {width_ft:g} ft x {thickness_in:g} in"
                ),
            )

        item["amt"] = amt
        subtotal += amt
        items.append(item)

    item_pages = []
    items_per_page = 12
    for page_start in range(0, len(items), items_per_page):
        page_items = items[page_start:page_start + items_per_page]
        for item in page_items:
            item["table_cells"] = _ply_item_table_cells(item)
        item_pages.append(page_items)

    taxes = _summarize_invoice_taxes(items, chcharge)
    subtotal = round(subtotal, 2)
    chcharge = round(chcharge, 2)
    taxable_value = round(subtotal + chcharge, 2)
    total_tax = taxes["cgst"] + taxes["sgst"] + taxes["igst"]
    grandtotal = math.ceil(taxable_value + total_tax)
    grandtotal_words = (num2words(grandtotal, lang='en_IN').replace(
        ' point ', ' and ')).replace(",", "").title() + " Only"
    context = {
        'invoice_no': "null",
        'date': date,
        'customer_name': customer_details["name"],
        'customer_namemetal': customer_details["name"],
        'customer_id': customer_id,
        'customer_type': customer_details["customer_type"],
        'GSTno': customer_details["gst_number"],
        'Address': customer_details["address"],
        'Address_lines': customer_details["address_lines"],
        'customer_mobile': customer_details["mobile"],
        'customer_email': customer_details["email"],
        'items': items,
        'product_types': list(dict.fromkeys(item["type"] for item in items)),
        'item_columns': PLY_ITEM_COLUMNS,
        'item_column_widths': PLY_ITEM_COLUMN_WIDTHS,
        'item_pages': item_pages,
        'subtotal': subtotal,
        'chcharge': round(chcharge, 2),
        "taxable_value": taxable_value,
        "tax_summary": taxes["summary"],
        "cgst": taxes["cgst"],
        "sgst": taxes["sgst"],
        "igst": taxes["igst"],
        "tax": taxes["cgst"],
        'grandtotal': grandtotal,
        'grandtotal_words': grandtotal_words,
        "raw_date": raw_date,
        "hsn": [item["hsn"] for item in items],
        "vehicle_number": request.form.get("vehicle_number", "").strip().upper(),
        "eway_bill_number": request.form.get("eway_bill_number", "").strip(),
        "transport_mode": request.form.get("transport_mode", "").strip(),
        "transporter_id": request.form.get("transporter_id", "").strip()
    }

    return context


def _request_pdf(rendered_html, **options):
    api_key = os.getenv("PDFBOLT_API_KEY") or os.getenv("pdf")
    if not api_key:
        raise RuntimeError("The PDF service API key is not configured.")
    response = requests.post(
        "https://api.pdfbolt.com/v1/direct",
        headers={"Content-Type": "application/json", "API_KEY": api_key},
        json={"html": base64.b64encode(rendered_html.encode("utf-8")).decode("ascii"),
              **options},
        timeout=60
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        try:
            error_response = response.json()
        except requests.exceptions.JSONDecodeError:
            error_response = {}
        if isinstance(error_response, dict):
            error_code = error_response.get("errorCode")
            error_message = error_response.get("errorMessage")
            details = "; ".join(
                str(value)[:300]
                for value in (error_code, error_message)
                if value
            )
        else:
            details = ""
        suffix = f": {details}" if details else ""
        raise RuntimeError(
            f"PDFBolt rejected the PDF request (HTTP {response.status_code}){suffix}"
        ) from exc
    if not response.content.startswith(b"%PDF-"):
        raise RuntimeError("The PDF service returned an invalid document.")
    return response.content


def _upload_pdf_content(pdf, filename, folder):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf)
        temp_path = tmp.name
    try:
        file_id, drive_link = upload_pdf(
            filepath=temp_path,
            filename=filename,
            to_folder=folder
        )
        if not file_id:
            raise RuntimeError("Google Drive did not return an uploaded file ID.")
        return file_id, drive_link
    finally:
        os.remove(temp_path)


class InvoiceProcessingError(RuntimeError):
    pass


def create_and_store_invoice(context, form_type):
    invoice_no, address = get_next_invoice_number_and_address(
        context["customer_id"], context
    )
    max_attempts = 5

    for attempt in range(max_attempts):
        if form_type == "Ply":
            context.update(invoice_no=invoice_no, Address=address)
            customer_name = context["customer_name"]
            invoice_date = context["date"]
        else:
            context.update(invoice_nometal=invoice_no, Addressmetal=address)
            customer_name = context["customer_namemetal"]
            invoice_date = context["datemetal"]

        filename = f"{invoice_no}-{customer_name}-{invoice_date.replace(' ', '')}.pdf"
        pdf = create_pdf(context, form_type=form_type)
        file_id, _ = _upload_pdf_content(pdf, filename, "invoice")
        payload = _invoice_record_payload(invoice_no, context)

        try:
            save_invoice_record(payload)
        except Exception as save_error:
            if _is_invoice_number_conflict(save_error):
                try:
                    delete_uploaded_pdf(file_id)
                except Exception as cleanup_error:
                    raise InvoiceProcessingError(
                        f"Invoice number {invoice_no} collided with another invoice, "
                        f"and temporary PDF {file_id} could not be removed from Drive. "
                        "Contact an administrator before retrying."
                    ) from cleanup_error
                if attempt + 1 == max_attempts:
                    raise InvoiceProcessingError(
                        "A unique invoice number could not be allocated after several "
                        "attempts. No PDF remains for the failed attempts; please retry."
                    ) from save_error
                invoice_no, address = get_next_invoice_number_and_address(
                    context["customer_id"], context
                )
                continue

            try:
                record_saved = invoice_record_matches(invoice_no, payload)
            except Exception as verification_error:
                raise InvoiceProcessingError(
                    f"Could not verify invoice {invoice_no} after a database error. "
                    f"PDF {file_id} remains in Drive; check the invoice record before retrying."
                ) from verification_error

            if record_saved:
                return invoice_no, filename

            try:
                delete_uploaded_pdf(file_id)
            except Exception as cleanup_error:
                raise InvoiceProcessingError(
                    f"Invoice {invoice_no} was not confirmed in the database, and PDF "
                    f"{file_id} could not be removed from Drive. Contact an administrator "
                    "before retrying."
                ) from cleanup_error
            raise InvoiceProcessingError(
                f"Invoice {invoice_no} was not saved. Its uploaded PDF was removed; "
                "you can retry."
            ) from save_error

        return invoice_no, filename

    raise InvoiceProcessingError("Invoice processing did not complete.")


def create_pdf(context, form_type):
    if (form_type == "Ply"):
        rendered_html = render_template('invoiceply.html', **context)
        return _request_pdf(
            rendered_html,
            scale=1,
            format="A4",
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            printBackground=True,
            emulateMediaType="print"
        )
    rendered_html = render_template('invoicemetal.html', **context)
    return _request_pdf(
        rendered_html,
        scale=0.65,
        format="A4",
        margin={
            "left": "250px"
        },
        emulateMediaType="print"
    )

@app.route("/generate", methods=["POST"])
@login_required
def generate_pdf():
    form_type = request.form.get('formSelector')
    if form_type not in ("Ply", "Metal"):
        flash("Select a valid invoice type.", "danger")
        return redirect(url_for("invoice_form"))
    try:
        context = generate_invoice() if form_type == "Ply" else generate_invoice_metal()
        _, name = create_and_store_invoice(context, form_type)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("invoice_form"))
    except InvoiceProcessingError as exc:
        app.logger.exception("Invoice processing compensation was required.")
        flash(str(exc), "danger")
        return redirect(url_for("invoice_form"))
    except Exception:
        app.logger.exception("Invoice generation failed.")
        flash(
            "Invoice generation did not complete. Check the invoice record and Drive "
            "before retrying.",
            "danger"
        )
        return redirect(url_for("invoice_form"))

    flash(f"📄 {name} created and uploaded successfully! ", "success")
    return redirect(url_for("invoice_form"))


@app.route("/preview", methods=["POST"])
@login_required
def preview_invoice():
    form_type = request.form.get("formSelector")
    try:
        if form_type == "Ply":
            context = generate_invoice()
            customer_details = get_customer_invoice_details(context["customer_id"])
            context.update(
                Address=customer_details["address"],
                Address_lines=customer_details["address_lines"],
                customer_mobile=customer_details["mobile"],
                customer_email=customer_details["email"],
            )
            return render_template("invoiceply.html", **context)
        if form_type == "Metal":
            context = generate_invoice_metal()
            customer_details = get_customer_invoice_details(context["customer_id"])
            context.update(
                Addressmetal=customer_details["address"],
                Address_lines=customer_details["address_lines"],
                customer_mobile=customer_details["mobile"],
                customer_email=customer_details["email"],
            )
            return render_template("invoicemetal.html", **context)
        flash("Select a valid invoice type.", "danger")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception:
        app.logger.exception("Invoice preview failed.")
        flash("Could not load the invoice preview. Please try again.", "danger")
    return redirect(url_for("invoice_form"))


@app.route("/add", methods=["POST"])
@login_required
def add_customer():
    allowed_users = ["admin"]  # Add allowed users here
    if current_user.id not in allowed_users:  # Adjust according to your user model
        return "Unauthorized", 403  # Or redirect to a custom error page
    name = request.form.get("name", "").strip()
    customer_type = request.form.get("customer_type", "").strip().lower()
    gst_number = request.form.get("gst_number", "").strip().upper()
    customer = {
        field: request.form.get(field, "").strip()
        for field in (
            "address_line_1",
            "address_line_2",
            "area_landmark",
            "city_village_district",
            "state",
            "pincode",
            "mobile",
            "email",
        )
    }
    required_fields = (
        ("address_line_1", "Address line 1"),
        ("city_village_district", "City/Village/District"),
        ("state", "State"),
        ("pincode", "Pincode"),
    )
    for field, label in required_fields:
        if not customer[field]:
            flash(f"{label} is required.", "danger")
            return redirect(url_for("analytics"))
    if not name or customer_type not in {"business", "retail"}:
        flash("Enter a customer name and select a valid customer type.", "danger")
        return redirect(url_for("analytics"))
    if customer_type == "business" and not gst_number:
        flash("GST number is required for GST-registered customers.", "danger")
        return redirect(url_for("analytics"))
    if customer_type == "retail" and gst_number:
        flash("Retail customers must not have a GST number.", "danger")
        return redirect(url_for("analytics"))
    if gst_number and not re.fullmatch(
        r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]", gst_number
    ):
        flash("Enter a valid 15-character GSTIN.", "danger")
        return redirect(url_for("analytics"))
    if customer["pincode"] and (
        len(customer["pincode"]) != 6 or not customer["pincode"].isdigit()
    ):
        flash("Pincode must contain exactly 6 digits.", "danger")
        return redirect(url_for("analytics"))
    if customer["mobile"] and (
        len(customer["mobile"]) != 10
        or not customer["mobile"].isdigit()
        or customer["mobile"][0] not in "6789"
    ):
        flash("Enter a valid 10-digit mobile number.", "danger")
        return redirect(url_for("analytics"))
    if customer["email"] and not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+", customer["email"]
    ):
        flash("Enter a valid email address.", "danger")
        return redirect(url_for("analytics"))

    supabase = connection()  # returns a Supabase Client

    payload = {
        "customer_type": customer_type,
        "name": name,
        "gst_number": gst_number or None,
        **customer,
    }
    try:
        supabase.table("customer").insert(payload).execute()
        flash("Customer added successfully!", "success")
        return redirect(url_for("analytics"))
    except Exception:
        app.logger.exception("Customer creation failed.")
        flash("Could not add the customer. Please try again.", "danger")
        return redirect(url_for("analytics"))
    # 5) Redirect to analytics page


@app.route("/analysis/pdf", methods=["POST"])
@login_required
def analysis_pdf():
    allowed_users = ["admin"]  # Add allowed users here
    if current_user.id not in allowed_users:  # Adjust according to your user model
        return "Unauthorized", 403
    datefrom = request.form.get("datefrom")
    dateto = request.form.get("dateto")
    customer_id = request.form.get("customer_id", "")
    selected_customer_name = None

    for label, value in (("start", datefrom), ("end", dateto)):
        if value:
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                flash(f"Enter a valid {label} date.", "danger")
                return redirect(url_for("analytics"))
    if datefrom and dateto and datefrom > dateto:
        flash("The start date must be on or before the end date.", "danger")
        return redirect(url_for("analytics"))

    supabase = connection()  # returns Supabase client
    query = supabase.table("invoice_data") \
        .select(
            "invoice_no, gst_number, customer_id, date, total_taxable_value, "
            "cgst, sgst, igst, grand_total, hsn, customer(name)"
        ) \
        .order("invoice_no", desc=False)

    if customer_id:
        selected_customer = next(
            (customer for customer in load_customers()
             if customer["customer_id"] == customer_id),
            None,
        )
        if not selected_customer:
            flash("Select a valid customer.", "danger")
            return redirect(url_for("analytics"))
        selected_customer_name = selected_customer["name"]
        query = query.eq("customer_id", customer_id)
    if datefrom:
        query = query.gte("date", datefrom)
    if dateto:
        query = query.lte("date", dateto)

    try:
        resp = query.execute()
    except Exception:
        app.logger.exception("Statement invoice query failed.")
        flash("Could not fetch invoices for the selected filters.", "danger")
        return redirect(url_for("analytics"))

    row = resp.data or []
    if not row:
        flash("No invoices found for those filters.", "warning")
        return redirect(url_for("analytics"))
    
    # Convert dictionaries to tuples in the order expected by the template
    formatted_results = []
    for inv in row:
        invoice_customer = inv.get("customer")
        invoice_customer_name = (
            invoice_customer.get("name", "")
            if isinstance(invoice_customer, dict) else ""
        )
        formatted_row = (
            inv.get("invoice_no"),
            inv.get("gst_number") or "RETAIL",
            invoice_customer_name,
            inv.get("date"),
            inv.get("total_taxable_value"),
            inv.get("cgst"),
            inv.get("sgst"),
            inv.get("igst") or 0,
            inv.get("grand_total"),
            inv.get("hsn")
        )
        formatted_results.append(formatted_row)
    
    # 3) Compute sums in Python
    total_cgst = sum(item[5] or 0 for item in formatted_results)
    total_sgst = sum(item[6] or 0 for item in formatted_results)
    total_igst = sum(item[7] or 0 for item in formatted_results)
    total_tax = total_cgst + total_sgst + total_igst
    total_taxable = sum(item[4] or 0 for item in formatted_results)
    total_grand = sum(item[8] or 0 for item in formatted_results)
    sums = (
        total_cgst, total_sgst, total_tax, total_taxable, total_grand, total_igst
    )

    # Render the same template into HTML string
    rendered_html = render_template("analysis_result.html",
                                    results=formatted_results,
                                    sums=sums)

    # Convert to PDF
    pdf = _request_pdf(rendered_html, emulateMediaType="print")

    if selected_customer_name:
        now = datetime.now()
        date_str = now.strftime("%d %B %Y").lstrip("0")
        name = f"{selected_customer_name}-{date_str}.pdf"
    else:
        if datefrom and dateto:
            date_from = datetime.strptime(datefrom, '%Y-%m-%d').strftime('%d %B %Y')
            date_to = datetime.strptime(dateto, '%Y-%m-%d').strftime('%d %B %Y')
            name = f"{date_from}-{date_to}.pdf"
        else:
            now = datetime.now()
            date_str = now.strftime("%d %B %Y").lstrip("0")
            name = f"Statement-{date_str}.pdf"
    _upload_pdf_content(pdf, name, "statement")

    flash(f"📄 {name} created and uploaded successfully! ", "success")
    # flash(f"<a href='{drive_link}' target='_blank'>View on Drive</a>", "info")
    # return send_file(
    #     io.BytesIO(pdf),
    #     download_name=f"{name}.pdf",
    #     as_attachment=True,
    #     mimetype='application/pdf'
    # )
    return redirect(url_for('analytics'))


# if __name__ == '__main__':
#     with app.app_context():
#         load_customers()
#     app.run(host='0.0.0.0', port=5500, debug=False)



if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000")) if is_render else int(
        os.getenv("APP_PORT", "5500")
    )
    app.run(
        host="0.0.0.0" if is_render else "127.0.0.1",
        port=port,
        debug=not is_render and os.getenv("FLASK_DEBUG", "").lower() == "true",
    )
