import os
import asyncio
import logging
import httpx
from datetime import datetime
from fastapi import APIRouter, Request, BackgroundTasks
from app.database import SessionLocal
from app.models import Product, ProductImage, UploadLog
from app.services.product_agent import parse_product, ProductData
from app.services.cloudinary_service import upload_image


def _log_upload(db, product_id: str, name: str, image_urls: list[str]) -> None:
    db.add(UploadLog(
        product_id=product_id,
        product_name=name,
        image_urls=image_urls,
        images_count=len(image_urls),
    ))
    db.commit()


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["telegram"])

# State per chat: "idle" | "waiting_text" | "waiting_images"
chat_states: dict[int, str] = {}

# chat_id -> {"text": str, "timestamp": int | None}
pending_texts: dict[int, dict] = {}

# media_group_id -> {"chat_id": int, "file_ids": list[str], "task": asyncio.Task | None}
pending_albums: dict[str, dict] = {}

_START_BUTTON = {
    "inline_keyboard": [[{"text": "📦 התחל העלאת מוצר", "callback_data": "start_upload"}]]
}


def _telegram_url(path: str) -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    return f"https://api.telegram.org/bot{token}/{path}"


async def _send_message(chat_id: int, text: str, reply_markup: dict = None) -> None:
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient() as client:
        await client.post(_telegram_url("sendMessage"), json=payload)


async def _answer_callback(callback_query_id: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(_telegram_url("answerCallbackQuery"), json={"callback_query_id": callback_query_id})


async def _download_photo(file_id: str) -> bytes:
    async with httpx.AsyncClient() as client:
        resp = await client.get(_telegram_url(f"getFile?file_id={file_id}"))
        file_path = resp.json()["result"]["file_path"]
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        download = await client.get(f"https://api.telegram.org/file/bot{token}/{file_path}")
        return download.content


async def _send_start_button(chat_id: int) -> None:
    await _send_message(
        chat_id,
        "ברוך הבא לבוט Ruty Store 👗\nלחץ על הכפתור להתחיל העלאת מוצר:",
        _START_BUTTON,
    )


async def _finalize_album(media_group_id: str) -> None:
    await asyncio.sleep(2)
    album = pending_albums.pop(media_group_id, None)
    if not album:
        return
    await _process_photos(album["chat_id"], album["file_ids"])


async def _process_photos(chat_id: int, file_ids: list[str]) -> None:
    pending = pending_texts.pop(chat_id, None)
    if not pending:
        await _send_message(chat_id, "❌ שגיאה פנימית — אין טקסט ממתין")
        chat_states[chat_id] = "idle"
        await _send_start_button(chat_id)
        return

    text = pending["text"]
    msg_date = pending["timestamp"]
    message_timestamp = datetime.fromtimestamp(msg_date) if msg_date else None

    await _send_message(chat_id, f"⏳ מעבד את המוצר ({len(file_ids)} תמונות)...")

    try:
        images_bytes: list[bytes] = await asyncio.gather(
            *[_download_photo(fid) for fid in file_ids]
        )

        data: ProductData = await parse_product(text=text, image_bytes=images_bytes[0])

        upload_results: list[dict] = await asyncio.gather(
            *[upload_image(img) for img in images_bytes]
        )

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

            for sort_order, result in enumerate(upload_results):
                db.add(ProductImage(
                    product_id=product.id,
                    cloudinary_url=result["url"],
                    cloudinary_public_id=result["public_id"],
                    sort_order=sort_order,
                ))
            db.commit()

            _log_upload(db, product.id, product.name, [r["url"] for r in upload_results])

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
            lines.append(f"🖼️ {len(upload_results)} תמונות נשמרו")
            lines.append(f"\n🔑 ID: {product.id}")
            await _send_message(chat_id, "\n".join(lines))
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error processing photos for chat {chat_id}: {e}", exc_info=True)
        await _send_message(chat_id, f"❌ שגיאה בעיבוד המוצר:\n{str(e)}")
    finally:
        chat_states[chat_id] = "idle"
        await _send_message(chat_id, "להעלות מוצר נוסף?", _START_BUTTON)


async def _process_update(update: dict) -> None:
    try:
        await _handle_update(update)
    except Exception as e:
        logger.error(f"Unhandled error in _process_update: {e}", exc_info=True)


async def _handle_update(update: dict) -> None:
    # Button press
    if "callback_query" in update:
        cq = update["callback_query"]
        chat_id = cq["message"]["chat"]["id"]
        await _answer_callback(cq["id"])
        if cq.get("data") == "start_upload":
            chat_states[chat_id] = "waiting_text"
            await _send_message(chat_id, "📝 שלח את טקסט המוצר")
        return

    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    if not chat_id:
        return

    text = message.get("text") or message.get("caption")
    photos = message.get("photo")
    media_group_id = message.get("media_group_id")
    msg_date = message.get("date")
    state = chat_states.get(chat_id, "idle")

    # /start or idle state — always show the button
    if text in ("/start", "/help") or state == "idle":
        chat_states[chat_id] = "idle"
        await _send_start_button(chat_id)
        return

    # Step 1: waiting for text
    if state == "waiting_text":
        if not text or photos:
            await _send_message(chat_id, "📝 שלח טקסט בלבד — ללא תמונות בשלב זה")
            return
        pending_texts[chat_id] = {"text": text, "timestamp": msg_date}
        chat_states[chat_id] = "waiting_images"
        await _send_message(chat_id, "📸 מעולה! עכשיו שלח את תמונות המוצר (אפשר אלבום של עד 10 תמונות)")
        return

    # Step 2: waiting for images
    if state == "waiting_images":
        if not photos:
            await _send_message(
                chat_id,
                "📸 שלח תמונות בלבד. אם רוצה להתחיל מחדש:",
                _START_BUTTON,
            )
            return

        largest = max(photos, key=lambda p: p.get("file_size", 0))
        file_id = largest["file_id"]

        if media_group_id:
            if media_group_id not in pending_albums:
                pending_albums[media_group_id] = {"chat_id": chat_id, "file_ids": [], "task": None}

            pending_albums[media_group_id]["file_ids"].append(file_id)

            old_task = pending_albums[media_group_id]["task"]
            if old_task and not old_task.done():
                old_task.cancel()

            pending_albums[media_group_id]["task"] = asyncio.create_task(
                _finalize_album(media_group_id)
            )
        else:
            await _process_photos(chat_id, [file_id])


@router.post("/telegram")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    update = await request.json()
    background_tasks.add_task(_process_update, update)
    return {"ok": True}
