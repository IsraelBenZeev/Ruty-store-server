import os
import re
import json
import base64
import logging
from typing import Optional, List
from pydantic import BaseModel, field_validator
from openai import AsyncOpenAI
from agents import Agent, Runner, trace
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

logger = logging.getLogger(__name__)


class ProductData(BaseModel):
    name: str
    description: Optional[str] = None
    source_message: Optional[str] = None
    price: Optional[float] = None
    brand: Optional[str] = None
    season: str = "all"
    gender: str = "כללי"
    size: Optional[List[str]] = None
    color: Optional[str] = None
    product_code: Optional[str] = None
    in_stock: bool = True
    delivery_time: Optional[str] = None
    allow_returns: Optional[bool] = None
    sms_required: Optional[bool] = None
    purchase_url: Optional[str] = None
    facebook_url: Optional[str] = None
    telegram_url: Optional[str] = None

    @field_validator("season", "gender", mode="before")
    @classmethod
    def coerce_none_to_default(cls, v, info):
        defaults = {"season": "all", "gender": "כללי"}
        return v if v is not None else defaults[info.field_name]


INSTRUCTIONS = """אתה סוכן AI של חנות בגדים ישראלית בשם Ruty Store.
תפקידך לנתח הודעות טקסט ותמונות של מוצרי ביגוד ולחלץ מהם נתונים מובנים.

חלץ את השדות הבאים:

- name: שם המוצר (חובה — כולל מותג ופרטים עיקריים, ללא ״מותג מוסתר״)
- description: תיאור קצר וממוקד של המוצר (1-3 משפטים) — סכם את הפרטים העיקריים: סוג הפריט, חומר, עיצוב, ייחוד. ללא מחיר, מידות, קישורים או הנחיות הזמנה
- source_message: הטקסט המלא של ההודעה כפי שהוא, מילה במילה (כולל אימוג׳י, כוכביות, מחיר, קישורים, הוראות הזמנה וכו׳)
- price: מחיר כמספר עשרוני (ללא ₪ / ש"ח / סימנים)
- brand: שם המותג האמיתי — חלץ אותו מתוך הטקסט גם אם כתוב ״מותג מוסתר״. ״מותג מוסתר״ הוא רק תיאור שיווקי, לא שם המותג. אם שם המותג מופיע בהמשך ההודעה (בשם המוצר, בתיאור, בסוף) — חלץ אותו. רק אם המותג לא מוזכר בכלל — החזר null
- season: אחד מ: winter, summer, all (ברירת מחדל: all)
- gender: תיאור מגדר חופשי בעברית, למשל: גברים, נשים, גברים ונשים, ילדים, נערים, כללי
- size: מערך של מידות בודדות. פרק טווחים לפריטים — "S-XXL" → ["S","M","L","XL","XXL"], "M-XXL" → ["M","L","XL","XXL"], "one size" → ["one size"]. סדר תמיד מהקטן לגדול.
- color: צבע/ים אם מוזכרים
- product_code: הקוד המזהה של המוצר — בדרך כלל שם + מספר בסוף ההודעה (למשל: "nancy A1907", "NANCY A2569")
- in_stock: true אם במלאי, false אם אזל (ברירת מחדל: true)
- delivery_time: זמן משלוח כטקסט חופשי אם מוזכר (למשל: "2-5 שבועות", "שבוע עד שבועיים"). null אם לא מוזכר
- allow_returns: false אם כתוב שאין החזרה/החלפה. true אם כן. null אם לא מוזכר
- sms_required: true אם כתוב שחובה להזמין עם מספר SMS / מספר לקבלת הודעות. false אם לא נדרש. null אם לא מוזכר
- purchase_url: קישור לרכישה (בדרך כלל flylinking.com או דומה)
- facebook_url: קישור לפוסט בפייסבוק אם קיים (facebook.com)
- telegram_url: קישור לפוסט בטלגרם אם קיים (t.me)

כללים:
- החזר אך ורק JSON תקין, ללא markdown ולא הסברים
- אם שדה לא מופיע — החזר null
- price חייב להיות מספר או null
- source_message = הטקסט המקורי המלא, שמור על שורות ואימוג׳י
- description ≠ source_message — description הוא תיאור מסוכם, לא העתק של ההודעה"""


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
