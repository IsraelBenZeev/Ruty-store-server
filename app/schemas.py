from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class ProductImageOut(BaseModel):
    id: str
    cloudinary_url: str
    sort_order: int

    model_config = {"from_attributes": True}


class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: Decimal
    season: str
    gender: str
    size: Optional[str] = None
    color: Optional[str] = None
    brand: Optional[str] = None
    in_stock: bool = True
    source_message: Optional[str] = None
    purchase_url: Optional[str] = None
    product_code: Optional[str] = None
    facebook_url: Optional[str] = None
    telegram_url: Optional[str] = None


class ProductCreate(ProductBase):
    pass


class ProductOut(ProductBase):
    id: str
    message_timestamp: Optional[datetime] = None
    created_at: Optional[datetime] = None
    images: List[ProductImageOut] = []

    model_config = {"from_attributes": True}
