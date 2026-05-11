import os
import re
import json
import base64
import logging
from typing import Optional, List
from pydantic import BaseModel
from openai import AsyncOpenAI
from agents import Agent, Runner, trace
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

logger = logging.getLogger(__name__)


class ProductData(BaseModel):
    name: str
    description: Optional[str] = None
    price: Optional[float] = None
    brand: Optional[str] = None
    season: str = "all"
    gender: str = "כללי"
    size: Optional[List[str]] = None
    color: Optional[str] = None
    product_code: Optional[str] = None
    in_stock: bool = True
    purchase_url: Optional[str] = None
    facebook_url: Optional[str] = None
    telegram_url: Optional[str] = None


INSTRUCTIONS = """אתה סוכן AI של חנות בגדים ישראלית בשם Ruty Store.
תפקידך לנתח הודעות טקסט ותמונות של מוצרי ביגוד ולחלץ מהם נתונים מובנים.

חלץ את השדות הבאים:

- name: שם המוצר (חובה — כולל מותג ופרטים עיקריים, ללא ״מותג מוסתר״)
- description: הטקסט המלא של ההודעה כפי שהוא (כולל אימוג׳י, כוכביות, הוראות וכו׳)
- price: מחיר כמספר עשרוני (ללא ₪ / ש"ח / סימנים)
- brand: שם המותג אם מוזכר במפורש. אם כתוב ״מותג מוסתר״ — החזר "מותג מוסתר"
- season: אחד מ: winter, summer, all (ברירת מחדל: all)
- gender: תיאור מגדר חופשי בעברית, למשל: גברים, נשים, גברים ונשים, ילדים, נערים, כללי
- size: מערך של מידות בודדות. פרק טווחים לפריטים — "S-XXL" → ["S","M","L","XL","XXL"], "M-XXL" → ["M","L","XL","XXL"], "one size" → ["one size"]. סדר תמיד מהקטן לגדול.
- color: צבע/ים אם מוזכרים
- product_code: הקוד המזהה של המוצר — בדרך כלל שם + מספר בסוף ההודעה (למשל: "nancy A1907", "NANCY A2569")
- in_stock: true אם במלאי, false אם אזל (ברירת מחדל: true)
- purchase_url: קישור לרכישה (בדרך כלל flylinking.com או דומה)
- facebook_url: קישור לפוסט בפייסבוק אם קיים (facebook.com)
- telegram_url: קישור לפוסט בטלגרם אם קיים (t.me)

כללים:
- החזר אך ורק JSON תקין, ללא markdown ולא הסברים
- אם שדה לא מופיע — החזר null
- price חייב להיות מספר או null
- description = הטקסט המקורי המלא, שמור על שורות ואימוג׳י"""


def _build_agent() -> Agent:
    client = AsyncOpenAI(
        api_key=os.getenv("GEMINI_API_KEY"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    model = OpenAIChatCompletionsModel(
        model="gemini-2.5-flash",
        openai_client=client,
    )
    return Agent(
        name="RutyStoreProductParser",
        instructions=INSTRUCTIONS,
        model=model,
    )


async def parse_product(text: str = None, image_bytes: bytes = None) -> ProductData:
    agent = _build_agent()

    content = []
    if image_bytes:
        b64 = base64.b64encode(image_bytes).decode()
        content.append({
            "type": "input_image",
            "image_url": f"data:image/jpeg;base64,{b64}",
        })
    content.append({"type": "input_text", "text": text or "נתח את המוצר"})

    with trace("parse_product", group_id="ruty-store"):
        result = await Runner.run(agent, [{"role": "user", "content": content}])

    raw = result.final_output or ""
    raw = re.sub(r"^```(?:json)?\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw).strip()
    return ProductData(**json.loads(raw))
