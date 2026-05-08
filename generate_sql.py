import json
import os

INPUT = os.path.join(os.path.dirname(__file__), "import_data.json")
OUTPUT = os.path.join(os.path.dirname(__file__), "insert_products.sql")

with open(INPUT, encoding="utf-8") as f:
    data = json.load(f)


def esc(val):
    if val is None:
        return "NULL"
    # Replace newlines with CHAR(10) so each INSERT stays on one line
    s = str(val).replace("'", "''")
    if "\n" in s:
        parts = s.split("\n")
        chunks = "+".join(f"N'{p}'" if p else "N''" for p in parts)
        # Join with CHAR(10)
        chunks = ("+CHAR(10)+").join(f"N'{p}'" for p in parts)
        return chunks
    return f"N'{s}'"


def parse_ts(ts_str):
    from datetime import datetime
    try:
        dt = datetime.strptime(ts_str, "%d.%m.%Y %H:%M:%S")
        return f"'{dt.strftime('%Y-%m-%d %H:%M:%S')}'"
    except Exception:
        return "NULL"


lines = []

for p in data:
    pid = p["id"]
    lines.append(
        f"INSERT INTO products (id,name,description,price,season,gender,size,brand,in_stock,source_message,"
        f"purchase_url,product_code,facebook_url,telegram_url,message_timestamp) VALUES ("
        f"{esc(pid)},{esc(p['name'])},{esc(p['description'])},{p['price']},{esc(p['season'])},"
        f"{esc(p['gender'])},{esc(p['size'])},{esc(p['brand'])},1,{esc(p['source_message'])},"
        f"{esc(p.get('purchase_url'))},{esc(p.get('product_code'))},{esc(p.get('facebook_url'))},"
        f"{esc(p.get('telegram_url'))},{parse_ts(p['message_timestamp'])});"
    )
    for img in p["images"]:
        lines.append(
            f"INSERT INTO product_images (id,product_id,cloudinary_url,cloudinary_public_id,original_filename,sort_order) VALUES ("
            f"{esc(img['id'])},{esc(pid)},{esc(img['cloudinary_url'])},{esc(img['cloudinary_public_id'])},"
            f"{esc(img['original_filename'])},{img['sort_order']});"
        )

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Generated {len(lines)} SQL statements -> {OUTPUT}")
