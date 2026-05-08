from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List
from app.database import get_db
from app.models import Product, ProductImage
from app.schemas import ProductCreate, ProductOut, ProductImageOut

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/", response_model=list[ProductOut])
def get_products(
    season: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    in_stock: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_asc: bool = Query(False),
    db: Session = Depends(get_db),
):
    q = db.query(Product)

    if season and season != "all-year":
        q = q.filter(or_(Product.season == season, Product.season == "all-year"))

    if gender and gender != "unisex":
        q = q.filter(or_(Product.gender == gender, Product.gender == "unisex"))

    if in_stock is not None:
        q = q.filter(Product.in_stock == in_stock)

    if search:
        term = f"%{search}%"
        q = q.filter(
            or_(
                Product.name.ilike(term),
                Product.brand.ilike(term),
                Product.description.ilike(term),
            )
        )

    sort_col = getattr(Product, sort_by, Product.created_at)
    q = q.order_by(sort_col.asc() if sort_asc else sort_col.desc())

    return q.all()


@router.get("/{product_id}/images", response_model=List[ProductImageOut])
def get_product_images(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product.images


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/", response_model=ProductOut, status_code=201)
def create_product(data: ProductCreate, db: Session = Depends(get_db)):
    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put("/{product_id}", response_model=ProductOut)
def update_product(product_id: str, data: ProductCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for key, value in data.model_dump().items():
        setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
