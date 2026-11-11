from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import jwt
import os
import requests
import logging
import json

from ..database import get_db
from .. import models

router = APIRouter()

JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-key-change-in-production")
ALGORITHM = "HS256"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

def get_telegram_chats():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    if not token:
        return []
    try:
        res = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=5)
        if res.ok:
            updates = res.json().get("result", [])
            chats = {}
            for u in updates:
                msg = u.get("message") or u.get("my_chat_member", {}).get("chat")
                if isinstance(msg, dict):
                    chat = msg.get("chat") if "chat" in msg else msg
                    if chat and "id" in chat:
                        cid = str(chat["id"])
                        c_title = chat.get("title") or chat.get("username") or f"{chat.get('first_name', '')} {chat.get('last_name', '')}".strip() or cid
                        chats[cid] = c_title
            return [{"id": cid, "name": name} for cid, name in chats.items()]
    except Exception as e:
        logging.error(f"Error fetching telegram chats: {e}")
    return []

def send_telegram_notification(msg_data: dict):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    if not token:
        return False
    
    chat_ids = []
    configured_id = os.environ.get("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID)
    if configured_id:
        chat_ids.append(configured_id)
    else:
        # Dynamically discover chats that wrote to the bot
        discovered = get_telegram_chats()
        chat_ids = [c["id"] for c in discovered]
        
    if not chat_ids:
        logging.warning("Telegram notification skipped: No chat_id configured and no chats found in getUpdates.")
        return False

    text = (
        f"🔔 <b>Нове звернення до правління ЖБК №102</b>\n\n"
        f"🏠 <b>Квартира:</b> № {msg_data.get('apt_number', '—')}\n"
        f"👤 <b>Мешканець:</b> {msg_data.get('resident_name') or '—'}\n"
        f"📞 <b>Телефон:</b> {msg_data.get('contact_phone') or '—'}\n"
        f"📂 <b>Категорія:</b> {msg_data.get('category') or 'Загальне'}\n"
    )
    if msg_data.get('subject'):
        text += f"📌 <b>Тема:</b> {msg_data['subject']}\n"
    text += f"\n💬 <b>Текст звернення:</b>\n<i>{msg_data.get('message', '')}</i>\n"
    text += f"\n⏱ <i>{datetime.now().strftime('%d.%m.%Y %H:%M')}</i>"

    success = False
    for cid in set(chat_ids):
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": cid,
                "text": text,
                "parse_mode": "HTML"
            }
            r = requests.post(url, json=payload, timeout=5)
            if r.ok:
                success = True
        except Exception as e:
            logging.error(f"Failed to send Telegram message to {cid}: {e}")
            
    return success

class MessageCreate(BaseModel):
    apartment_id: Optional[int] = None
    resident_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    category: str = "Загальне питання"
    subject: Optional[str] = None
    message: str

class MessageUpdate(BaseModel):
    status: Optional[str] = None
    admin_response: Optional[str] = None

def get_token_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            return None
        return db.query(models.UserAccess).filter(models.UserAccess.email == email).first()
    except Exception:
        return None

@router.get("/messages")
def list_messages(
    apartment_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: Optional[models.UserAccess] = Depends(get_token_user)
):
    query = db.query(models.ResidentMessage).options(joinedload(models.ResidentMessage.apartment))
    
    # If user is resident, restrict to their apartment
    if user and user.role == "resident":
        if user.apartment_id:
            query = query.filter(models.ResidentMessage.apartment_id == user.apartment_id)
        else:
            return []
    elif apartment_id is not None:
        query = query.filter(models.ResidentMessage.apartment_id == apartment_id)

    messages = query.order_by(models.ResidentMessage.created_at.desc()).all()
    
    res = []
    for m in messages:
        res.append({
            "id": m.id,
            "apartment_id": m.apartment_id,
            "apartment_number": m.apartment.number if m.apartment else "—",
            "resident_name": m.resident_name or (m.apartment.owner_name if m.apartment else ""),
            "contact_phone": m.contact_phone,
            "contact_email": m.contact_email,
            "category": m.category,
            "subject": m.subject,
            "message": m.message,
            "status": m.status or "new",
            "admin_response": m.admin_response,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None
        })
    return res

@router.post("/messages")
def create_message(
    msg: MessageCreate,
    db: Session = Depends(get_db),
    user: Optional[models.UserAccess] = Depends(get_token_user)
):
    if not msg.message or not msg.message.strip():
        raise HTTPException(status_code=400, detail="Повідомлення не може бути порожнім")
    
    apt_id = msg.apartment_id
    if user and user.role == "resident" and user.apartment_id:
        apt_id = user.apartment_id
    
    db_msg = models.ResidentMessage(
        apartment_id=apt_id,
        resident_name=msg.resident_name,
        contact_phone=msg.contact_phone,
        contact_email=msg.contact_email or (user.email if user else None),
        category=msg.category or "Загальне питання",
        subject=msg.subject,
        message=msg.message.strip(),
        status="new"
    )
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)

    # Send Telegram notification to board
    apt = db.query(models.Apartment).filter(models.Apartment.id == apt_id).first() if apt_id else None
    apt_num = apt.number if apt else "—"
    try:
        send_telegram_notification({
            "apt_number": apt_num,
            "resident_name": msg.resident_name or (apt.owner_name if apt else ""),
            "contact_phone": msg.contact_phone,
            "category": msg.category or "Загальне питання",
            "subject": msg.subject,
            "message": msg.message.strip()
        })
    except Exception as e:
        logging.error(f"Error triggering telegram notification: {e}")
    
    return {
        "id": db_msg.id,
        "status": "success",
        "message": "Звернення успішно надіслано правлінню ЖБК"
    }

@router.patch("/messages/{message_id}")
def update_message(
    message_id: int,
    update: MessageUpdate,
    db: Session = Depends(get_db),
    user: Optional[models.UserAccess] = Depends(get_token_user)
):
    if user and user.role == "resident":
        raise HTTPException(status_code=403, detail="Лише адміністратор може оновлювати статус звернень")
    
    db_msg = db.query(models.ResidentMessage).filter(models.ResidentMessage.id == message_id).first()
    if not db_msg:
        raise HTTPException(status_code=404, detail="Звернення не знайдено")
    
    if update.status is not None:
        db_msg.status = update.status
    if update.admin_response is not None:
        db_msg.admin_response = update.admin_response
        
    db.commit()
    db.refresh(db_msg)
    return {"status": "success", "message_id": db_msg.id, "new_status": db_msg.status}

@router.delete("/messages/{message_id}")
def delete_message(
    message_id: int,
    db: Session = Depends(get_db),
    user: Optional[models.UserAccess] = Depends(get_token_user)
):
    if user and user.role == "resident":
        raise HTTPException(status_code=403, detail="Лише адміністратор може видаляти звернення")
    
    db_msg = db.query(models.ResidentMessage).filter(models.ResidentMessage.id == message_id).first()
    if not db_msg:
        raise HTTPException(status_code=404, detail="Звернення не знайдено")
    
    db.delete(db_msg)
    db.commit()
    return {"status": "success", "deleted_id": message_id}


@router.get("/telegram/chats")
def list_telegram_chats():
    chats = get_telegram_chats()
    return {
        "configured_token": bool(TELEGRAM_BOT_TOKEN),
        "configured_chat_id": TELEGRAM_CHAT_ID or None,
        "discovered_chats": chats
    }

@router.post("/telegram/test")
def test_telegram_notification():
    ok = send_telegram_notification({
        "apt_number": "Тест",
        "resident_name": "Тестовий мешканець",
        "contact_phone": "+380500000000",
        "category": "Тестове сповіщення",
        "subject": "Перевірка зв'язку Telegram",
        "message": "Тестове сповіщення з системи ЖБК 102 «Заполяр'є» успішно доставлено!"
    })
    return {"success": ok}

DEFAULT_SUPPORT_CONTACTS = [
    {
        "id": "building_address",
        "icon": "fas fa-map-marker-alt",
        "category": "Адреса будинку",
        "title": "м. Дніпро, вул. Михайла Грушевського, 14",
        "subtitle": "ЖБК № 102 «Заполяр'є» (ЄДРПОУ 23025161)",
        "phone": "",
        "link": "",
        "is_emergency": False
    },
    {
        "id": "board_head",
        "icon": "fas fa-user-tie",
        "category": "Голова ЖБК",
        "title": "067 636 66 89",
        "subtitle": "",
        "phone": "067 636 66 89",
        "link": "",
        "is_emergency": False
    },
    {
        "id": "accountant",
        "icon": "fas fa-calculator",
        "category": "Бухгалтер ЖБК",
        "title": "098 206 09 31",
        "subtitle": "Субота: 12:00 – 16:00 (Олена Олександрівна)",
        "phone": "098 206 09 31",
        "link": "",
        "is_emergency": False
    },
    {
        "id": "emergency_dispatcher",
        "icon": "fas fa-tools",
        "category": "Аварійний диспетчер (загальні місця та прибудинкова територія)",
        "title": "096 132 32 42 · 067 132 32 42 · 063 132 32 42 · 099 132 32 42",
        "subtitle": "Цілодобово",
        "phone": "096 132 32 42",
        "link": "",
        "is_emergency": True
    },
    {
        "id": "elevator",
        "icon": "fas fa-angle-double-up",
        "category": "Диспетчер з обслуговування ліфтів",
        "title": "056 790 99 50 · 067 523 65 58 · 099 357 53 49",
        "subtitle": "Цілодобово",
        "phone": "056 790 99 50",
        "link": "",
        "is_emergency": False
    },
    {
        "id": "gas",
        "icon": "fas fa-burn",
        "category": "Газова обслуговуюча компанія",
        "title": "067 890 56 60",
        "subtitle": "Цілодобово",
        "phone": "067 890 56 60",
        "link": "",
        "is_emergency": False
    },
    {
        "id": "water",
        "icon": "fas fa-faucet",
        "category": "Контролер Водоканалу (Вікторія)",
        "title": "095 789 45 59 · 068 874 35 97",
        "subtitle": "",
        "phone": "095 789 45 59",
        "link": "",
        "is_emergency": False
    },
    {
        "id": "dnipro_hotline",
        "icon": "fas fa-exclamation-triangle",
        "category": "Цілодобова єдина гаряча лінія для звернень громадян",
        "title": "1530",
        "subtitle": "Офіційний веб-портал звернень громадян м. Дніпро",
        "phone": "1530",
        "link": "https://hotline.dniprorada.gov.ua/personalcabinet/createrequest",
        "is_emergency": True
    }
]

class ContactItem(BaseModel):
    id: Optional[str] = None
    icon: Optional[str] = "fas fa-info-circle"
    category: str
    title: str
    subtitle: Optional[str] = ""
    phone: Optional[str] = ""
    link: Optional[str] = ""
    is_emergency: Optional[bool] = False

@router.get("/contacts")
def get_support_contacts(db: Session = Depends(get_db)):
    setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "support_contacts").first()
    if setting and setting.value:
        try:
            return json.loads(setting.value)
        except Exception as e:
            logging.error(f"Error parsing support_contacts JSON: {e}")
    return DEFAULT_SUPPORT_CONTACTS

@router.put("/contacts")
def save_support_contacts(
    contacts: List[ContactItem],
    db: Session = Depends(get_db),
    user: Optional[models.UserAccess] = Depends(get_token_user)
):
    if user and user.role == "resident":
        raise HTTPException(status_code=403, detail="Лише адміністратор може редагувати контакти")
    
    contacts_data = [c.dict() for c in contacts]
    setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "support_contacts").first()
    if not setting:
        setting = models.SystemSetting(key="support_contacts", value=json.dumps(contacts_data, ensure_ascii=False))
        db.add(setting)
    else:
        setting.value = json.dumps(contacts_data, ensure_ascii=False)
    
    db.commit()
    return {"status": "success", "contacts": contacts_data}

