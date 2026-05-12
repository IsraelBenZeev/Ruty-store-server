import os
import asyncio
import cloudinary
import cloudinary.uploader


async def upload_image(image_bytes: bytes) -> dict:
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    )
    result = await asyncio.to_thread(
        cloudinary.uploader.upload,
        image_bytes,
        folder="Ruty-store",
        resource_type="image",
    )
    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
    }
