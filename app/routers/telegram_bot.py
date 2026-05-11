import os
import logging
import httpx
from datetime import datetime
from fastapi import APIRouter, Request, BackgroundTasks
from app.database import SessionLocal
from app.models import Product
from app.services.product_agent import parse_product, ProductData

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["telegram"])


def _telegram_url(path: str) -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    return f"https://api.telegram.org/bot{token}/{path}"


async def _send_message(chat_id: int, text: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(_telegram_url("sendMessage"), json={"chat_id": chat_id, "text": text})


async def _download_photo(file_id: str) -> bytes:
    async with httpx.AsyncClient() as client:
        resp = await client.get(_telegram_url(f"getFile?file_id={file_id}"))
        file_path = resp.json()["result"]["file_path"]
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        download = await client.get(f"https://api.telegram.org/file/bot{token}/{file_path}")
        return download.content


async def _process_update(update: dict) -> None:
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    if not chat_id:
        return

    text = message.get("text") or message.get("caption")
    photos = message.get("photo")

    if not text and not photos:
        await _send_message(chat_id, "שלח תמונה של מוצר (עם כיתוב אם יש) או טקסט עם פרטי המוצר.")
        return

    await _send_message(chat_id, "⏳ מעבד את המוצר...")

    try:
        image_bytes = None
        if photos:
            largest = max(photos, key=lambda p: p.get("file_size", 0))
            image_bytes = await _download_photo(largest["file_id"])

        data: ProductData = await parse_product(text=text, image_bytes=image_bytes)

        msg_date = message.get("date")
        message_timestamp = datetime.fromtimestamp(msg_date) if msg_date else None

        size_pg = ("{" + ",".join(data.size) + "}") if data.size else None

        db = SessionLocal()
        try:
            product = Product(
                name=data.name or "מוצר ללא שם",
                description=data.description,
                price=data.price or 0,
                season=data.season or "all",
                gender=data.gender or "כללי",
                size=size_pg,
                color=data.color,
                brand=data.brand,
                product_code=data.product_code,
                in_stock=data.in_stock,
                source_message=text,
                purchase_url=data.purchase_url,
                facebook_url=data.facebook_url,
                telegram_url=data.telegram_url,
                message_timestamp=message_timestamp,
            )
            db.add(product)
            db.commit()
            db.refresh(product)

            lines = ["✅ מוצר נוסף בהצלחה!\n", f"📦 {product.name}"]
            if product.price:
                lines.append(f"💰 ₪{product.price}")
            if product.brand:
                lines.append(f"🏷️ {product.brand}")
            if product.size:
                lines.append(f"📏 {product.size}")
            if product.color:
                lines.append(f"🎨 {product.color}")
            if product.purchase_url:
                lines.append(f"🔗 {product.purchase_url}")
            lines.append(f"\n🔑 ID: {product.id}")
            await _send_message(chat_id, "\n".join(lines))
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error processing Telegram update: {e}")
        await _send_message(chat_id, f"❌ שגיאה בעיבוד המוצר:\n{str(e)}")


@router.post("/telegram")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    update = await request.json()
    background_tasks.add_task(_process_update, update)
    return {"ok": True}
