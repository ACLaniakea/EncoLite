"""Select an exact product image; never substitute another earphone model."""
from pathlib import Path
import re


def product_image(root, product_id, custom_root=None):
    root=Path(root)
    if re.fullmatch(r'[0-9A-Fa-f]{6}',product_id or ''):
        identifier=product_id.upper()
        candidates=[]
        if custom_root:
            candidates.append(Path(custom_root)/identifier/'product.png')
        candidates.append(root/'ui/assets/models'/f'{identifier}.png')
        for path in candidates:
            if path.is_file():
                return path
    return root/'ui/assets/device-neutral.svg'
