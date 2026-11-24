import os
import base64
import logging
from datetime import datetime, timedelta
from typing import List, Tuple
import email as email_lib
from email import policy as email_policy

import json
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow, Flow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GMAIL_API_AVAILABLE = True
except ImportError:
    GMAIL_API_AVAILABLE = False

os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid',
]


def get_client_config(db=None):
    """Load Google OAuth client credentials from DB, env vars, or file."""
    # 1. DB
    if db:
        try:
            from ..models import SystemSetting
            setting = db.query(SystemSetting).filter(SystemSetting.key == "gmail_credentials_json").first()
            if setting and setting.value:
                return json.loads(setting.value)
        except Exception as e:
            logger.warning(f"Failed to load credentials from DB: {e}")

    # 2. Env GMAIL_CREDENTIALS_JSON
    env_json = os.getenv("GMAIL_CREDENTIALS_JSON")
    if env_json:
        try:
            return json.loads(env_json)
        except Exception as e:
            logger.warning(f"Failed to parse GMAIL_CREDENTIALS_JSON: {e}")

    # 3. File
    creds_path = os.getenv('GMAIL_CREDENTIALS', 'credentials.json')
    if os.path.exists(creds_path):
        try:
            with open(creds_path, 'r', encoding='utf-8') as f:
                content = f.read()
                data = json.loads(content)
                if db:
                    try:
                        from ..models import SystemSetting
                        setting = db.query(SystemSetting).filter(SystemSetting.key == "gmail_credentials_json").first()
                        if not setting:
                            db.add(SystemSetting(key="gmail_credentials_json", value=content))
                            db.commit()
                            logger.info("Auto-seeded gmail_credentials_json into DB from file.")
                    except Exception as se:
                        logger.debug(f"Could not auto-seed credentials to DB: {se}")
                return data
        except Exception as e:
            logger.warning(f"Failed to read {creds_path}: {e}")

    # 4. GMAIL_CLIENT_ID & GMAIL_CLIENT_SECRET
    cid = os.getenv("GMAIL_CLIENT_ID")
    csecret = os.getenv("GMAIL_CLIENT_SECRET")
    if cid and csecret:
        return {
            "web": {
                "client_id": cid,
                "client_secret": csecret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
    return None


def get_gmail_service(db=None):
    if not GMAIL_API_AVAILABLE:
        raise ImportError("Google API client libraries not installed. Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")

    creds = None
    close_db = False
    if db is None:
        try:
            from ..database import SessionLocal
            db = SessionLocal()
            close_db = True
        except Exception:
            pass

    token_json_str = None
    if db:
        try:
            from ..models import SystemSetting
            setting = db.query(SystemSetting).filter(SystemSetting.key == "gmail_token_json").first()
            if setting and setting.value:
                token_json_str = setting.value
        except Exception as e:
            logger.warning(f"Failed to load token from DB: {e}")

    if not token_json_str:
        token_json_str = os.getenv('GMAIL_TOKEN_JSON')

    if token_json_str:
        try:
            token_data = json.loads(token_json_str)
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        except Exception as e:
            logger.warning(f"Failed to load credentials from token JSON: {e}")

    token_path = os.getenv('GMAIL_TOKEN', 'token.json')
    if not creds and os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            if creds and db:
                try:
                    from ..models import SystemSetting
                    setting = db.query(SystemSetting).filter(SystemSetting.key == "gmail_token_json").first()
                    if not setting:
                        db.add(SystemSetting(key="gmail_token_json", value=creds.to_json()))
                        db.commit()
                        logger.info("Auto-seeded gmail_token_json into DB from file.")
                except Exception as se:
                    logger.debug(f"Could not auto-seed token to DB: {se}")
        except Exception as e:
            logger.warning(f"Failed to load credentials from {token_path}: {e}")
    
    refresh_error = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                token_json_updated = creds.to_json()
                if db:
                    try:
                        from ..models import SystemSetting
                        setting = db.query(SystemSetting).filter(SystemSetting.key == "gmail_token_json").first()
                        if not setting:
                            db.add(SystemSetting(key="gmail_token_json", value=token_json_updated))
                        else:
                            setting.value = token_json_updated
                        db.commit()
                    except Exception as se:
                        logger.warning(f"Could not update refreshed token in DB: {se}")
                try:
                    with open(token_path, 'w') as token:
                        token.write(token_json_updated)
                except Exception as write_err:
                    logger.debug(f"Could not save refreshed token to file: {write_err}")
            except Exception as e:
                logger.warning(f"Failed to refresh Gmail token: {e}. Token needs re-authentication.")
                refresh_error = e
                creds = None

        if not creds:
            if close_db and db:
                db.close()
            if refresh_error:
                raise RuntimeError(f"Термін дії токена Google закінчився ({refresh_error}). Будь ласка, перейдіть у 'Налаштування' та натисніть кнопку 'Авторизувати Gmail'.")
            raise RuntimeError("Gmail не авторизовано. Будь ласка, перейдіть у розділ 'Налаштування' та натисніть кнопку 'Авторизувати Gmail'.")

    if close_db and db:
        db.close()

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


def fetch_registry_emails(from_date: str, to_date: str, db=None) -> List[Tuple[str, bytes]]:
    """Fetch PrivatBank registry text attachments from Gmail.
    
    Handles two scenarios:
    1. Email with a direct .txt attachment (normal case)
    2. Email with .eml attachments, each containing a .txt registry inside
    
    Args:
        from_date: YYYY-MM-DD format
        to_date: YYYY-MM-DD format
        db: Optional database session
        
    Returns:
        List of tuples: (message_id, attachment_bytes)
    """
    if not GMAIL_API_AVAILABLE:
        logger.warning("Gmail API not available. Cannot fetch emails.")
        return []

    service = get_gmail_service(db=db)
    
    # Format date for Gmail search
    from_dt = datetime.strptime(from_date, "%Y-%m-%d").strftime("%Y/%m/%d")
    # Add 1 day to to_date for inclusive search
    to_dt_obj = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)
    to_dt = to_dt_obj.strftime("%Y/%m/%d")
    
    query = f'(23025161 OR "Вивантаження" OR reestr) has:attachment after:{from_dt} before:{to_dt}'
    
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
