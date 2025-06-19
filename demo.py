import os
import json
from google.oauth2 import service_account
from dotenv import load_dotenv
load_dotenv()
# json_str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")

# # Convert JSON string to dict
# creds_dict = json.loads(json_str)
# print(creds_dict)
# # Use service_account_info instead of a file
# creds = service_account.Credentials.from_service_account_info(creds_dict)