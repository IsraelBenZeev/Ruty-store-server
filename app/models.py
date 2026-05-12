from sqlalchemy import Column, String, Numeric, Boolean, Text, DateTime, Integer, ForeignKey, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    season = Column(String(20), nullable=False)
    gender = Column(String(20), nullable=False)
    size = Column(String(50), nullable=True)
    color = Column(String(100), nullable=True)
    brand = Column(String(100), nullable=True)
    in_stock = Column(Boolean, nullable=False, default=True)
    delivery_time = Column(String(100), nullable=True)
    allow_returns = Column(Boolean, nullable=True)
    sms_required = Column(Boolean, nullable=True)
    source_message = Column(Text, nullable=True)
    purchase_url = Column(String(500), nullable=True)
    product_code = Column(String(100), nullable=True)
    facebook_url = Column(String(500), nullable=True)
    telegram_url = Column(String(500), nullable=True)
    message_timestamp = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    images = relationship("ProductImage", back_populates="product", order_by="ProductImage.sort_order", cascade="all, delete-orphan")


class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    cloudinary_url = Column(String(500), nullable=False)
    cloudinary_public_id = Column(String(255), nullable=True)
    original_filename = Column(String(255), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())

    product = relationship("Product", back_populates="images")


class ProductTemp(Base):
    __tablename__ = "products_temp"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    season = Column(String(20), nullable=False)
    gender = Column(String(20), nullable=False)
    size = Column(String(50), nullable=True)
    color = Column(String(100), nullable=True)
    brand = Column(String(100), nullable=True)
    in_stock = Column(Boolean, nullable=False, default=True)
    delivery_time = Column(String(100), nullable=True)
    allow_returns = Column(Boolean, nullable=True)
    sms_required = Column(Boolean, nullable=True)
    source_message = Column(Text, nullable=True)
    purchase_url = Column(String(500), nullable=True)
    product_code = Column(String(100), nullable=True)
    facebook_url = Column(String(500), nullable=True)
    telegram_url = Column(String(500), nullable=True)
    message_timestamp = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    images = relationship("ProductImageTemp", back_populates="product", order_by="ProductImageTemp.sort_order", cascade="all, delete-orphan")


class ProductImageTemp(Base):
    __tablename__ = "product_images_temp"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(String(36), ForeignKey("products_temp.id", ondelete="CASCADE"), nullable=False)
    cloudinary_url = Column(String(500), nullable=False)
    cloudinary_public_id = Column(String(255), nullable=True)
    original_filename = Column(String(255), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())

    product = relationship("ProductTemp", back_populates="images")


class UploadLog(Base):
    __tablename__ = "upload_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String(36), nullable=False)
    product_name = Column(String(255), nullable=False)
    image_urls = Column(ARRAY(String), nullable=False, default=list)
    images_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())
