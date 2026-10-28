import hashlib
from typing import Any, Dict, List, Optional


async def asset_hash(asset_ref: str) -> str:
    return hashlib.sha256(asset_ref.encode("utf-8")).hexdigest()


async def inspect_media(asset_ref: str) -> Dict[str, Any]:
    """Return media metadata + derived frame refs.

    Live implementations use FFmpeg / provider upload; mock returns stable refs.
    """
    digest = await asset_hash(asset_ref)
    return {
        "asset_ref": asset_ref,
        "asset_hash": digest,
        "duration_seconds": 15.0,
        "aspect_ratio": "9:16",
        "audio_present": True,
        "frames": [f"frame://{digest[:12]}/t=1", f"frame://{digest[:12]}/t=3", f"frame://{digest[:12]}/t=5"],
        "mode": "FRAME_SAMPLE",
    }


async def extract_frames(asset_ref: str, timestamps: List[float]) -> List[str]:
    digest = await asset_hash(asset_ref)
    return [f"frame://{digest[:12]}/t={t}" for t in timestamps]


async def extract_transcript(asset_ref: str) -> Optional[str]:
    return None  # mock: no transcript until audio pipeline configured
