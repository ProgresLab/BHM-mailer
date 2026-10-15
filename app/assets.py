"""Private immutable campaign images. Names come from the validated bytes, never uploads."""
import hashlib
import io
import os
from pathlib import Path
import re
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
from .db import UPLOADS_DIR

ASSET_DIR = Path(os.getenv('BHM_ASSET_DIR', UPLOADS_DIR / 'campaign_assets'))
MAX_UPLOAD = 5 * 1024 * 1024


def asset_path(asset_id: str) -> Path:
    if not re.fullmatch(r'[a-f0-9]{64}\.(jpg|png)', asset_id or ''):
        raise ValueError('Nieprawidłowy identyfikator grafiki.')
    return ASSET_DIR / asset_id


def store_banner(data: bytes) -> str:
    if not data or len(data) > MAX_UPLOAD:
        raise ValueError('Baner: maksymalnie 5 MB; zalecane poniżej 300 KB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as probe:
                if probe.format not in {'JPEG', 'PNG'}:
                    raise ValueError('Baner musi być rzeczywistym JPG lub PNG.')
                if probe.width * probe.height > 12000000 or max(probe.size) > 6000:
                    raise ValueError('Baner przekracza bezpieczne wymiary (maksymalnie 6000×2000 px).')
                probe.verify()
            with Image.open(io.BytesIO(data)) as original:
                image = ImageOps.exif_transpose(original)
                width, height = image.size
                if width < 600 or height < 200 or width > 6000 or height > 2000 or abs(width / height - 3) > .03:
                    raise ValueError('Wymagane proporcje 3:1, od 600×200 do 6000×2000 px; zalecane 1200×400 px. Obraz nie jest kadrowany.')
                image.thumbnail((1200, 400), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                if 'A' in image.getbands():
                    image.save(output, 'PNG', optimize=True)
                    ext = 'png'
                else:
                    image.convert('RGB').save(output, 'JPEG', quality=85, optimize=True)
                    ext = 'jpg'
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('Nie można odczytać bezpiecznego obrazu JPG/PNG.') from exc
    encoded = output.getvalue()
    key = hashlib.sha256(encoded).hexdigest() + '.' + ext
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    path = asset_path(key)
    if not path.exists():
        # Same bytes always have the same name; historical assets are never deleted.
        path.write_bytes(encoded)
    return key


def banner_cid(asset_id: str) -> str:
    asset_path(asset_id)
    return 'bhm-banner-' + asset_id
