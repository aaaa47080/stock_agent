import os
from PIL import Image

image_path = "d:/okx/stock_agent/web/img/title_icon.png"
if os.path.exists(image_path):
    print(f"Original size: {os.path.getsize(image_path) / 1024:.2f} KB")
    try:
        with Image.open(image_path) as img:
            # Resize to max 250px width, maintaining aspect ratio
            base_width = 250
            w_percent = (base_width / float(img.size[0]))
            h_size = int((float(img.size[1]) * float(w_percent)))
            img = img.resize((base_width, h_size), Image.Resampling.LANCZOS)
            
            # Save optimized
            img.save(image_path, optimize=True, quality=85)
            print(f"Resized image saved.")
            print(f"New size: {os.path.getsize(image_path) / 1024:.2f} KB")
    except Exception as e:
        print(f"Error resizing image: {e}")
else:
    print("Image not found.")
