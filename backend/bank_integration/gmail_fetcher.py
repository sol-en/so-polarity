import os
import base64
import logging
from datetime import datetime, timedelta
from typing import List, Tuple
import email as email_lib
from email import policy as email_policy

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GMAIL_API_AVAILABLE = True
except ImportError:
    GMAIL_API_AVAILABLE = False

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    if not GMAIL_API_AVAILABLE:
        raise ImportError("Google API client libraries not installed. Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")

    creds = None
    token_path = os.getenv('GMAIL_TOKEN', 'token.json')
    creds_path = os.getenv('GMAIL_CREDENTIALS', 'credentials.json')

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.warning(f"Failed to refresh Gmail token: {e}. Removing invalid token and re-authenticating...")
                if os.path.exists(token_path):
                    try:
                        os.remove(token_path)
                    except Exception as rm_err:
                        logger.warning(f"Could not remove invalid token file: {rm_err}")
                creds = None

        if not creds:
            if not os.path.exists(creds_path):
                raise FileNotFoundError(f"Credentials file {creds_path} not found.")
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


def _extract_txt_from_eml(eml_bytes: bytes) -> List[bytes]:
    """Parse a raw .eml file and return all .txt attachment contents found inside it."""
    txt_files = []
    try:
        msg = email_lib.message_from_bytes(eml_bytes, policy=email_policy.compat32)
        for part in msg.walk():
            filename = part.get_filename() or ''
            content_type = part.get_content_type()
            # Match .txt files or text/plain attachments named like registries
            if filename.lower().endswith('.txt') or (content_type == 'text/plain' and filename):
                payload = part.get_payload(decode=True)
                if payload:
                    txt_files.append(payload)
                    logger.info(f"Extracted txt '{filename}' ({len(payload)} bytes) from .eml")
    except Exception as e:
        logger.warning(f"Failed to parse .eml content: {e}")
    return txt_files


def fetch_registry_emails(from_date: str, to_date: str) -> List[Tuple[str, bytes]]:
    """Fetch PrivatBank registry text attachments from Gmail.
    
    Handles two scenarios:
    1. Email with a direct .txt attachment (normal case)
    2. Email with .eml attachments, each containing a .txt registry inside
    
    Args:
        from_date: YYYY-MM-DD format
        to_date: YYYY-MM-DD format
        
    Returns:
        List of tuples: (message_id, attachment_bytes)
    """
    if not GMAIL_API_AVAILABLE:
        logger.warning("Gmail API not available. Cannot fetch emails.")
        return []

    service = get_gmail_service()
    
    # Format date for Gmail search
    from_dt = datetime.strptime(from_date, "%Y-%m-%d").strftime("%Y/%m/%d")
    # Add 1 day to to_date for inclusive search
    to_dt_obj = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)
    to_dt = to_dt_obj.strftime("%Y/%m/%d")
    
    query = f'subject:(Вивантаження реєстру ПриватБанк 23025161) has:attachment after:{from_dt} before:{to_dt}'
    
    logger.info(f"Searching Gmail with query: {query}")
    
    results = service.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])
    
    attachments = []

    def _get_part_bytes(part, msg_id) -> bytes:
        """Download a MIME part's payload bytes."""
        if 'data' in part['body']:
            data = part['body']['data']
        else:
            att_id = part['body']['attachmentId']
            att = service.users().messages().attachments().get(
                userId='me', messageId=msg_id, id=att_id).execute()
            data = att['data']
        return base64.urlsafe_b64decode(data.encode('UTF-8'))

    def extract_attachments(parts, msg_id):
        """Recursively walk MIME parts, collecting .txt files directly or via .eml wrappers."""
        for part in parts:
            filename = part.get('filename') or ''
            mime_type = part.get('mimeType', '')

            # Case 1: direct .txt attachment
            if filename.lower().endswith('.txt') and part['body'].get('size', 0) > 0:
                file_data = _get_part_bytes(part, msg_id)
                attachments.append((msg_id, file_data))
                logger.info(f"Found direct .txt: {filename} ({len(file_data)} bytes) in msg {msg_id}")

            # Case 2: .eml attachment — parse it to find the nested .txt
            elif filename.lower().endswith('.eml') or mime_type in ('message/rfc822', 'application/octet-stream'):
                if filename.lower().endswith('.eml') and part['body'].get('size', 0) > 0:
                    eml_bytes = _get_part_bytes(part, msg_id)
                    logger.info(f"Found .eml attachment: {filename} ({len(eml_bytes)} bytes) in msg {msg_id}")
                    nested_txts = _extract_txt_from_eml(eml_bytes)
                    for txt_data in nested_txts:
                        attachments.append((msg_id, txt_data))

            # Recurse into nested MIME parts
            if 'parts' in part:
                extract_attachments(part['parts'], msg_id)

    for message in messages:
        msg_id = message['id']
        msg = service.users().messages().get(userId='me', id=msg_id).execute()
        extract_attachments(msg['payload'].get('parts', []), msg_id)
                
    return attachments
