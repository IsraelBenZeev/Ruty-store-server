import os
import json
import re
import google.generativeai as genai

SYSTEM_PROMPT = """אתה סוכן AI של חנות בגדים ישראלית בשם Ruty Store.
תפקידך לנתח הודעות טקסט ותמונות של מוצרי ביגוד ולחלץ מהם נתונים מובנים.

חלץ את השדות הבאים:
- name: שם המוצר (חובה - אם לא ברור, תאר קצר מהתמונה)
- description: תיאור מלא של המוצר
- price: מחיר כמספר עשרוני בלבד (ללא ₪ או סימנים, למשל: 149.90)
- brand: מותג אם מוזכר
- season: עונה - אחד מ: winter, summer, all-year
- gender: מגדר - אחד מ: גברים, נשים, ילדים, נערים, כללי
- size: מידה כמחרוזת (למשל: "M", "38", "XL", "52/54", "one size")
- color: צבע/צבעים
- product_code: קוד מוצר אם קיים
- in_stock: האם במלאי (true/false, ברירת מחדל true)

כללים חשובים:
- החזר אך ורק JSON תקין, ללא markdown, ללא הסברים
- אם שדה לא מופיע בהודעה, השתמש ב-null
- price חייב להיות מספר (לא מחרוזת) או null
- in_stock חייב להיות boolean

דוגמה לפלט:
{
  "name": "חולצת פולו כחולה",
  "description": "חולצת פולו קלאסית בצבע כחול נייבי",
  "price": 89.90,
  "brand": "Tommy Hilfiger",
  "season": "all-year",
  "gender": "גברים",
  "size": "L",
  "color": "כחול נייבי",
  "product_code": "TH-2024-001",
  "in_stock": true
}"""


def parse_product(text: str = None, image_bytes: bytes = None) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=SYSTEM_PROMPT,
    )

    parts = []

    if image_bytes:
        parts.append({"mime_type": "image/jpeg", "data": image_bytes})

    parts.append(text or "נתח את התמונה וחלץ פרטי מוצר")

    response = model.generate_content(parts)
    raw = response.text.strip()

    # Strip markdown code blocks if Gemini wraps the response
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)

    return json.loads(raw.strip())
