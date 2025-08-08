from flask import Flask, render_template, redirect, url_for, request,send_file,Response,jsonify,flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user,current_user
import pdfkit
import pickle
from num2words import num2words
import base64
import requests
from supabase import create_client,Client
import tempfile
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request 
from google_auth_oauthlib.flow import InstalledAppFlow   
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from reportlab.lib.pagesizes import A4


load_dotenv()
# INVOICE_FOLDER_ID   = os.getenv("INVOICE_FOLDER_ID")
# STATEMENT_FOLDER_ID = os.getenv("STATEMENT_FOLDER_ID")
SERVICE_ACCOUNT_EMAIL = os.getenv("SERVICE_ACCOUNT_EMAIL")
SCOPES = ["https://www.googleapis.com/auth/drive"]
TOKEN_PATH = 'token.pickle'
CREDENTIALS_PATH = 'credentials.json'
def get_drive_service():
    """
    Authenticates using the service account key pointed to by
    GOOGLE_APPLICATION_CREDENTIALS and returns a Drive v3 service.
    """
    creds = None
    # 2) Load cached credentials if they exist
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token_file:
            creds = pickle.load(token_file)

    # 3) If there are no valid creds, run the flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=8080)
        # 4) Save the credentials for next time
        with open(TOKEN_PATH, 'wb') as token_file:
            pickle.dump(creds, token_file)

    # 5) Build and return the Drive service
    return build('drive', 'v3', credentials=creds, cache_discovery=False)

    # creds = service_account.Credentials.from_service_account_file(
    #     os.environ["GOOGLE_APPLICATION_CREDENTIALS"], scopes=SCOPES
    # )
    # return build("drive", "v3", credentials=creds, cache_discovery=False)
def upload_pdf(filepath: str, filename: str, to_folder: str) -> str:
    """
    Uploads a PDF to Drive into the specified folder.
    Returns the fileId.
    to_folder should be either 'invoice' or 'statement'.
    """
    INVOICE_FOLDER_ID   = os.getenv("INVOICE_FOLDER_ID")
    STATEMENT_FOLDER_ID = os.getenv("STATEMENT_FOLDER_ID")

    service = get_drive_service()
    folder_id = INVOICE_FOLDER_ID if to_folder.lower() == 'invoice' else STATEMENT_FOLDER_ID

    file_metadata = {
        'name': filename,
        'parents': [folder_id],
    }
    media = MediaFileUpload(filepath, mimetype='application/pdf')

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink',
        supportsAllDrives=True
    ).execute()

    return file['id'], file['webViewLink']

app = Flask(__name__)
app.config['WTF_CSRF_SECRET_KEY'] = os.getenv("WTF_CSRF_SECRET_KEY")
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY environment variable not set!")
if not app.config["WTF_CSRF_SECRET_KEY"]:
    raise RuntimeError("WTF_CSRF_SECRET_KEY environment variable not set!")
csrf = CSRFProtect(app)


@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf)


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


customer_cache = []


def load_customers():
    global customer_cache
    # conn =connection()
    # cur = conn.cursor()
    # cur.execute("SELECT gst,name FROM customer")
    # rows = cur.fetchall()
    # cur.close()
    # conn.close()
    # customer_cache = [[r[0],r[1]] for r in rows]
    supabase = connection()

    response = supabase.table("customer").select("gst,name").execute()
    customer_cache = [[item["gst"], item["name"]] for item in response.data]

    # customer_cache = [{ "gst": r[0],"name": r[1]} for r in rows]


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
def writetopdf(formtype, **context):
    supabase = connection()  # now returns a Supabase Client

    # 1) Fetch customer address
    resp = supabase.table("customer") \
        .select("address") \
        .eq("gst", context["GSTno"]) \
        .single() \
        .execute()
    address = resp.data.get("address", "").strip().replace("\n", "")
    # 2) Compute next invoice_no
    resp = supabase.table("invoice_data") \
        .select("invoice_no") \
        .order("invoice_no", desc=True) \
        .limit(1) \
        .execute()

    last_invoice = resp.data[0]["invoice_no"] if resp.data else 0
    next_invoice = last_invoice + 1

    # 3) Prepare payload for insertion
    payload = {
        "invoice_no": next_invoice,
        "gst": context["GSTno"],
        "date": context["raw_date"],
        "hsn": context["hsn"],
        "total_taxable_value": context["taxable_value"],
        "cgst": context["tax"],
        "sgst": context["tax"],
        "grand_total": context["grandtotal"]
    }

    # Insert the invoice record
    try:
        supabase.table("invoice_data") \
        .insert(payload) \
        .execute()
        return next_invoice, address
    except Exception as e:
        return jsonify({"status": "error", "message": e}), 500


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
            load_customers()
            user = User(username)
            login_user(user)
            load_customers()
            return redirect(url_for('invoice_form'))
        flash("Invalid credentials", "danger")
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/', methods=['GET'])
@login_required
def invoice_form():
    load_customers()
    return render_template('invoice_form.html', customers=customer_cache)


@app.route("/analysis", methods=["GET", "POST"])
@login_required
def analytics():
    return render_template("analytics.html", customers=customer_cache)


def generate_invoice_metal():
    # Read form data
    raw_date = request.form['datemetal']  # e.g. "2025-04-30"
    date_obj = datetime.strptime(raw_date, '%Y-%m-%d')
    date = date_obj.strftime('%d %B %Y')  # e.g. "30 April 2025"
    # invoice_no = request.form['invoice_nometal']
    GSTno, customer_name = request.form['customer_namemetal'].split("|")
    GSTno = GSTno.strip()
    # GSTno = request.form['GSTmetal']
    # Address = requestadd(GSTno)
    chcharge = float(request.form["chchargemetal"])

    # items = [json.loads(x) for x in request.form.getlist("itemsmetal[]")]

    items = []
    hsnlist = []
    subtotal = 0.0
    for idx, js in enumerate(request.form.getlist('itemsmetal[]'), start=1):
        desc, hsn, qty, priceperkg = json.loads(js)
        amt = priceperkg * qty
        subtotal = subtotal + amt
        hsnlist.append(hsn)
        items.append({
            'no': idx,
            'desc': desc,
            'hsn': hsn,
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
        'customer_namemetal': customer_name,
        'GSTno': GSTno,
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
    # Read form data
    raw_date = request.form['date']
    date_obj = datetime.strptime(raw_date, '%Y-%m-%d')
    date = date_obj.strftime('%d %B %Y')  # e.g. "30 April 2025"
    # invoice_no = request.form['invoice_no']
    GSTno, customer_name = request.form['customer_name'].split("|")
    # GSTno=GSTno.replace(" ","")
    # GSTno = request.form['GST']
    # Address =
    chcharge = float(request.form["chcharge"])

    items = [json.loads(x) for x in request.form.getlist("items[]")]
    hsnlist = [44123190]
    items = []
    subtotal = 0.0
    for idx, js in enumerate(request.form.getlist('items[]'), start=1):
        desc, length_ft, width_ft, qty, price_per_sqft = json.loads(js)
        l = length_ft * .3048
        b = width_ft * .3048
        pr = price_per_sqft / 0.09290304
        area = l * b * qty
        amt = area * pr
        subtotal = subtotal + amt

        items.append({
            'no': idx,
            'desc': desc,
            'l': round(l, 2),
            'b': round(b, 2),
            'hsn': '44123190',
            'qty': qty,
            'area': round(area, 3),
            'unit': 'sq.mtr',
            'pr': round(pr, 3),
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
        'invoice_no': "null",
        'date': date,
        'customer_name': customer_name,
        'GSTno': GSTno,
        'Address': "Address",
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


def create_pdf(context, form_type):
    if (form_type == "Ply"):
        rendered_html = render_template('invoiceply.html', **context)
        html = base64.b64encode(rendered_html.encode("utf-8")).decode("ascii")
        payload = {
            "html": html,
            "scale": 0.7,  # 80% zoom
            "format": "A4",
            "margin": {
                "left": "5px"
            },
            # "preferCssPageSize": True,
            "emulateMediaType": "print"
        }
    else:
        rendered_html = render_template('invoicemetal.html', **context)
        html = base64.b64encode(rendered_html.encode("utf-8")).decode("ascii")
        payload = {
            "html": html,
            "scale": 0.65,  # 80% zoom
            "format": "A4",
            "margin": {
                "left": "250px"
            },
            # "preferCssPageSize": True,
            "emulateMediaType": "print"
        }
    url = 'https://api.pdfbolt.com/v1/direct'
    headers = {
        'Content-Type': 'application/json',
        'API_KEY': os.getenv("pdf1")
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.content


@app.route("/generate", methods=["POST", "GET"])
@login_required
def generate_pdf():
    form_type = request.form.get('formSelector')
    if (form_type == "Ply"):
        context = generate_invoice()
        invoicenum, add = writetopdf(formtype=form_type, **context)
        context['invoice_no'] = invoicenum
        context['Address'] = add
        pdf = create_pdf(context, form_type=form_type)
        name = f"{invoicenum}-{context['customer_name']}-{(context['date']).replace(' ','')}.pdf".replace(
            "\n", "")
    else:
        context = generate_invoice_metal()
        invoicenum, add = writetopdf(formtype=form_type, **context)
        context['invoice_nometal'] = invoicenum
        context['Addressmetal'] = add
        pdf = create_pdf(context, form_type=form_type)
        name = f"{invoicenum}-{context['customer_namemetal']}-{(context['datemetal']).replace(' ','')}.pdf".replace(
            "\n", "")
    # 6) Send PDF to client
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf)
        tmp.flush()
        temp_path = tmp.name
    folder_key = "invoice"
    file_id, drive_link = upload_pdf(filepath=temp_path,
                                     filename=name,
                                     to_folder=folder_key)

    # 4) Clean up
    os.remove(temp_path)

    # 5) Flash success (with optional link)
    flash(f"📄 {name} created and uploaded successfully! ", "success")
    # flash(f"<a href='{drive_link}' target='_blank'>View on Drive</a>", "info")

    return redirect(url_for("invoice_form"))
    # return send_file(
    #     io.BytesIO(pdf),
    #     download_name=name,
    #     as_attachment=True,
    #     mimetype='application/pdf'
    # )


@app.route("/preview", methods=["POST"])
@login_required
def preview_invoice():
    form_type = request.form.get("formSelector")
    if (form_type == "Ply"):
        context = generate_invoice()
        return render_template("invoiceply.html", **context)
    else:
        context = generate_invoice_metal()
        return render_template("invoicemetal.html", **context)


@app.route("/add", methods=["POST"])
@login_required
def add_customer():
    allowed_users = ["admin"]  # Add allowed users here
    if current_user.id not in allowed_users:  # Adjust according to your user model
        return "Unauthorized", 403  # Or redirect to a custom error page
    name = request.form["name"]
    gst = request.form["gst"]
    add = request.form["Address"]

    supabase = connection()  # returns a Supabase Client

    # 3) Insert into 'customer' table
    payload = {"gst": gst, "name": name, "address": add}
    try:
        supabase.table("customer").insert(payload).execute()
        load_customers()
        flash("Customer added successfully!", "success")
        return redirect(url_for("analytics"))
    except Exception as e:
        # Handle insertion error
        flash(f"Error adding customer: {e}", "danger")
        return redirect(url_for("analytics"))
    # 5) Redirect to analytics page


@app.route("/analysis/pdf", methods=["POST"])
@login_required
def analysis_pdf():
    allowed_users = ["admin"]  # Add allowed users here
    if current_user.id not in allowed_users:  # Adjust according to your user model
        return "Unauthorized", 403
    # We expect the same form data here:
    customer_name = "null"
    datefrom = request.form.get("datefrom")
    dateto = request.form.get("dateto")
    gstcustomer = request.form.get("gstcustomer", "")

    supabase = connection()  # returns Supabase client
    query = supabase.table("invoice_data") \
        .select("invoice_no, gst, date, total_taxable_value, cgst, sgst, grand_total, hsn, customer(name)") \
        .order("invoice_no", desc=False)

    if gstcustomer:
        GSTno, customer_name = gstcustomer.split("|")
        query = query.eq("gst", GSTno)
    if datefrom:
        query = query.gte("date", datefrom)
    if dateto:
        query = query.lte("date", dateto)

    try:
        resp = query.execute()
    except Exception as e:
        flash(f"Error fetching invoices: {e}", "danger")
        return redirect(url_for("analytics"))

    row = resp.data or []
    if not row:
        flash("No invoices found for those filters.", "warning")
        return redirect(url_for("analytics"))
    for inv in row:
        # Move nested customer.name up
        inv["customer_name"] = inv.get("customer", {}).get("name", "")
        # Remove the nested dict
        inv.pop("customer", None)
    # 3) Compute sums in Python
    total_cgst = sum(item["cgst"] for item in row)
    total_sgst = sum(item["sgst"] for item in row)
    total_tax = sum(item["cgst"] + item["sgst"] for item in row)
    total_taxable = sum(item["total_taxable_value"] for item in row)
    total_grand = sum(item["grand_total"] for item in row)
    sums = (total_cgst, total_sgst, total_tax, total_taxable, total_grand)

    # Render the same template into HTML string
    rendered_html = render_template("analysis_result.html",
                                    results=row,
                                    sums=sums)

    # Convert to PDF
    html = base64.b64encode(rendered_html.encode("utf-8")).decode("ascii")
    payload = {
        "html": html,
        # "scale": 0.7,  # 80% zoom
        # "format": "A4",
        # "margin": {
        #     "left": "5px"
        # },
        # "preferCssPageSize": True,
        "emulateMediaType": "print"
    }
    url = 'https://api.pdfbolt.com/v1/direct'
    headers = {
        'Content-Type': 'application/json',
        'API_KEY': os.getenv("pdf1")
    }
    pdf = (requests.post(url, headers=headers, json=payload)).content

    if not customer_name == "null":
        now = datetime.now()
        date_str = now.strftime("%d %B %Y").lstrip("0")
        name = f"{customer_name}-{date_str}"
    else:
        date_from_ = datetime.strptime(datefrom, '%Y-%m-%d')
        date_from = date_from_.strftime('%d %B %Y')
        date_to_ = datetime.strptime(dateto, '%Y-%m-%d')
        date_to = date_to_.strftime('%d %B %Y')
        name = f"{date_from}-{date_to}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf)
        tmp.flush()
        temp_path = tmp.name
    folder_key = "statement"
    file_id, drive_link = upload_pdf(filepath=temp_path,
                                     filename=name,
                                     to_folder=folder_key)

    # 4) Clean up
    os.remove(temp_path)

    # 5) Flash success (with optional link)
    flash(f"📄 {name} created and uploaded successfully! ", "success")
    # flash(f"<a href='{drive_link}' target='_blank'>View on Drive</a>", "info")
    # return send_file(
    #     io.BytesIO(pdf),
    #     download_name=f"{name}.pdf",
    #     as_attachment=True,
    #     mimetype='application/pdf'
    # )
    return redirect(url_for('analytics'))


if __name__ == '__main__':
    with app.app_context():
        load_customers()
    app.run(host='0.0.0.0', port=5500, debug=False)

