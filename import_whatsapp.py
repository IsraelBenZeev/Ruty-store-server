import os
import re
import uuid
import json
import cloudinary
import cloudinary.uploader
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

CHAT_DIR = os.path.join(os.path.dirname(__file__), "WhatsApp Chat - קניות")
CHAT_FILE = os.path.join(CHAT_DIR, "_chat.txt")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "import_data.json")
CLOUDINARY_FOLDER = "Ruty-store"

MSG_RE = re.compile(r"^\[(\d{1,2}\.\d{1,2}\.\d{4}), (\d{1,2}:\d{2}:\d{2})\] ([^:]+): (.*)")
IMG_RE = re.compile(r"^<מצורף: ([\w\-\.]+\.jpg)>")


def detect_gender(text):
    parts = []
    if re.search(r"גבר|לגברים", text):
        parts.append("גברים")
    if re.search(r"נשים|לנשים", text):
        parts.append("נשים")
    if re.search(r"נער(?!ות)|לנערים", text):
        parts.append("נערים")
    if re.search(r"נערות|לנערות", text):
        parts.append("נערות")
    if re.search(r"ילד|לילדים", text):
        parts.append("ילדים")
    result = " ו".join(parts) if parts else "כללי"
    return result[:20]


def detect_season(text):
    if re.search(r"קיץ|קיצי|שרוול קצר|summer", text, re.IGNORECASE):
        return "summer"
    if re.search(r"חורף|חורפי|winter|מעיל", text, re.IGNORECASE):
        return "winter"
    if re.search(r"מעבר|אביב|סתיו|spring|fall|autumn", text, re.IGNORECASE):
        return "spring"
    return "all"


def parse_product_text(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    name = None
    brand = "מותג מוסתר"

    for i, line in enumerate(lines):
        if "מותג" in line:
            for j in range(i + 1, len(lines)):
                c = lines[j]
                if c and not c.startswith("*") and not c.startswith("http") and "מידות" not in c and "מחיר" not in c:
                    name = c
                    break
            break

    if not name:
        for line in lines:
            if line and not line.startswith("*") and not line.startswith("http") and "מידות" not in line:
                name = line
                break

    price_match = re.search(r"מחיר(?:\s+מבצע)?[:\s]+(\d+)", text)
    price = float(price_match.group(1)) if price_match else 0.0

    size_match = re.search(r"מידות?[:\s]+([^\n]+)", text)
    size = size_match.group(1).strip() if size_match else ""
    size = re.sub(r"\s*מחיר.*", "", size).strip()[:50]

    purchase_match = re.search(r"(https?://store\.flylinking\.com/\S+)", text)
    purchase_url = purchase_match.group(1) if purchase_match else None

    code_match = re.search(r"\b([A-Za-z]{2,}\s+[A-Z]{1,3}\d{3,})\b", text)
    product_code = code_match.group(1).upper() if code_match else None

    fb_match = re.search(r"(https?://www\.facebook\.com/\S+)", text)
    facebook_url = fb_match.group(1).rstrip("/") if fb_match else None

    tg_match = re.search(r"(https?://t\.me/\S+)", text)
    telegram_url = tg_match.group(1) if tg_match else None

    return {
        "name": (name or "ללא שם")[:255],
        "brand": brand[:100],
        "price": price,
        "size": size,
        "gender": detect_gender(text),
        "season": detect_season(text),
        "purchase_url": purchase_url,
        "product_code": product_code,
        "facebook_url": facebook_url,
        "telegram_url": telegram_url,
        "source_message": text,
    }


def parse_chat(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    content = re.sub(r"[‎‏‪-‮]", "", content)
    lines = content.split("\n")

    products = []
    pending_images = []

    i = 0
    while i < len(lines):
        line = lines[i]
        msg_match = MSG_RE.match(line)

        if not msg_match:
            i += 1
            continue

        date_str, time_str, _sender, content = msg_match.groups()
        timestamp_str = f"{date_str} {time_str}"
        content = content.strip()

        img_match = IMG_RE.match(content)
        if img_match:
            pending_images.append(img_match.group(1))
            i += 1
            continue

        full_text = content
        i += 1
        while i < len(lines) and not MSG_RE.match(lines[i]):
            full_text += "\n" + lines[i]
            i += 1

        if "מחיר" in full_text and "flylinking" in full_text:
            product = parse_product_text(full_text)
            product["images"] = pending_images.copy()
            product["message_timestamp"] = timestamp_str
            products.append(product)
            pending_images = []

    return products


def upload_image(image_path, product_code):
    folder = f"{CLOUDINARY_FOLDER}/{product_code or 'misc'}"
    result = cloudinary.uploader.upload(image_path, folder=folder, resource_type="image")
    return result["secure_url"], result["public_id"]


def main():
    print("Parsing WhatsApp chat...")
    products = parse_chat(CHAT_FILE)
    print(f"Found {len(products)} products\n")

    output = []
    total_images = sum(len(p["images"]) for p in products)
    uploaded = 0
    skipped = 0

    for idx, product in enumerate(products, 1):
        product_id = str(uuid.uuid4())
        print(f"[{idx}/{len(products)}] product_code={product.get('product_code')} images={len(product['images'])}")

        uploaded_images = []
        for order, filename in enumerate(product["images"]):
            image_path = os.path.join(CHAT_DIR, filename)
            if not os.path.exists(image_path):
                print(f"  [WARN] Not found: {filename}")
                skipped += 1
                continue
            try:
                url, public_id = upload_image(image_path, product.get("product_code"))
                uploaded_images.append({
                    "id": str(uuid.uuid4()),
                    "product_id": product_id,
                    "cloudinary_url": url,
                    "cloudinary_public_id": public_id,
                    "original_filename": filename,
                    "sort_order": order,
                })
                print(f"  [OK] {filename} -> {url}")
                uploaded += 1
            except Exception as e:
                print(f"  [ERR] {filename}: {e}")
                skipped += 1

        output.append({
            "id": product_id,
            "name": product["name"],
            "description": product["source_message"],
            "price": product["price"],
            "season": product["season"],
            "gender": product["gender"],
            "size": product["size"],
            "brand": product["brand"],
            "purchase_url": product.get("purchase_url"),
            "product_code": product.get("product_code"),
            "facebook_url": product.get("facebook_url"),
            "telegram_url": product.get("telegram_url"),
            "message_timestamp": product["message_timestamp"],
            "source_message": product["source_message"],
            "images": uploaded_images,
        })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 50}")
    print(f"Products: {len(output)}")
    print(f"Images uploaded: {uploaded}")
    print(f"Images skipped:  {skipped}")
    print(f"Output saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
