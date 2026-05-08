import json
import os
import uuid
import pyodbc
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

CONN_STR = (
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={os.getenv('AZURE_SQL_SERVER')};"
    f"DATABASE={os.getenv('AZURE_SQL_DATABASE')};"
    f"UID={os.getenv('AZURE_SQL_USERNAME')};"
    f"PWD={os.getenv('AZURE_SQL_PASSWORD')};"
    "Encrypt=yes;TrustServerCertificate=no;"
)

INPUT = os.path.join(os.path.dirname(__file__), "import_data.json")

with open(INPUT, encoding="utf-8") as f:
    data = json.load(f)

conn = pyodbc.connect(CONN_STR)
cursor = conn.cursor()

success = 0
errors = 0

for idx, p in enumerate(data, 1):
    print(f"[{idx}/{len(data)}] {p['product_code']}")
    try:
        try:
            ts = datetime.strptime(p["message_timestamp"], "%d.%m.%Y %H:%M:%S")
        except Exception:
            ts = None

        cursor.execute("""
            INSERT INTO products (id,name,description,price,season,gender,size,brand,
                in_stock,source_message,purchase_url,product_code,facebook_url,telegram_url,message_timestamp)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            p["id"], p["name"], p["description"], p["price"], p["season"],
            p["gender"], p["size"], p["brand"], 1, p["source_message"],
            p.get("purchase_url"), p.get("product_code"),
            p.get("facebook_url"), p.get("telegram_url"), ts
        ))

        for img in p["images"]:
            cursor.execute("""
                INSERT INTO product_images (id,product_id,cloudinary_url,cloudinary_public_id,original_filename,sort_order)
                VALUES (?,?,?,?,?,?)
            """, (
                img["id"], p["id"], img["cloudinary_url"],
                img["cloudinary_public_id"], img["original_filename"], img["sort_order"]
            ))

        conn.commit()
        print(f"  [OK] {len(p['images'])} images")
        success += 1

    except Exception as e:
        conn.rollback()
        print(f"  [ERR] {e}")
        errors += 1

cursor.close()
conn.close()

print(f"\n{'='*40}")
print(f"Success: {success}  Errors: {errors}")
