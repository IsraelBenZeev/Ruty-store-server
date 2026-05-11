import json
import os
import urllib.request
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set in .env")

host = DATABASE_URL.split("@")[1].split("/")[0]
SQL_URL = f"https://{host}/sql"
HEADERS = {"Content-Type": "application/json", "Neon-Connection-String": DATABASE_URL}

INPUT = os.path.join(os.path.dirname(__file__), "import_data.json")


def run_sql(query, params=None):
    body = json.dumps({"query": query, "params": params or []}).encode()
    req = urllib.request.Request(SQL_URL, data=body, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


with open(INPUT, encoding="utf-8") as f:
    data = json.load(f)

print("Creating tables...")

run_sql("""
    CREATE TABLE IF NOT EXISTS products (
        id VARCHAR(36) PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        price NUMERIC(10,2) NOT NULL,
        season VARCHAR(20) NOT NULL,
        gender VARCHAR(20) NOT NULL,
        size VARCHAR(50),
        color VARCHAR(100),
        brand VARCHAR(100),
        in_stock BOOLEAN NOT NULL DEFAULT TRUE,
        source_message TEXT,
        purchase_url VARCHAR(500),
        product_code VARCHAR(100),
        facebook_url VARCHAR(500),
        telegram_url VARCHAR(500),
        message_timestamp TIMESTAMP,
        created_at TIMESTAMP DEFAULT NOW()
    )
""")

run_sql("""
    CREATE TABLE IF NOT EXISTS product_images (
        id VARCHAR(36) PRIMARY KEY,
        product_id VARCHAR(36) NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        cloudinary_url VARCHAR(500) NOT NULL,
        cloudinary_public_id VARCHAR(255),
        original_filename VARCHAR(255),
        sort_order INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW()
    )
""")

print("Tables ready. Inserting data...")

success = 0
errors = 0

for idx, p in enumerate(data, 1):
    print(f"[{idx}/{len(data)}] {p.get('product_code') or p['name'][:40]}")
    try:
        ts = None
        if p.get("message_timestamp"):
            try:
                ts = datetime.strptime(p["message_timestamp"], "%d.%m.%Y %H:%M:%S").isoformat()
            except Exception:
                pass

        run_sql(
            """INSERT INTO products
               (id,name,description,price,season,gender,size,color,brand,
                in_stock,source_message,purchase_url,product_code,
                facebook_url,telegram_url,message_timestamp)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
               ON CONFLICT (id) DO NOTHING""",
            [
                p["id"], p["name"], p.get("description"),
                float(p["price"]), p["season"], p["gender"],
                p.get("size"), p.get("color"), p.get("brand"),
                True, p.get("source_message"), p.get("purchase_url"),
                p.get("product_code"), p.get("facebook_url"),
                p.get("telegram_url"), ts,
            ],
        )

        for img in p.get("images", []):
            run_sql(
                """INSERT INTO product_images
                   (id,product_id,cloudinary_url,cloudinary_public_id,original_filename,sort_order)
                   VALUES ($1,$2,$3,$4,$5,$6)
                   ON CONFLICT (id) DO NOTHING""",
                [
                    img["id"], p["id"], img["cloudinary_url"],
                    img.get("cloudinary_public_id"), img.get("original_filename"),
                    int(img.get("sort_order", 0)),
                ],
            )

        print(f"  [OK] {len(p.get('images', []))} images")
        success += 1

    except Exception as e:
        print(f"  [ERR] {e}")
        errors += 1

print(f"\n{'='*40}")
print(f"Success: {success}  Errors: {errors}")
