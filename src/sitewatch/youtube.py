import os
import re
from typing import Any, Dict, Optional, Tuple

import yt_dlp

os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "protocol_whitelist;file,crypto,data,http,https,tcp,tls",
)

_YT = re.compile(
    r"^(https?://)?(www\.|m\.)?(youtube\.com|youtu\.be)/", re.IGNORECASE
)
MAX_HEIGHT = 720


def is_youtube(text: str) -> bool:
    return bool(_YT.match(text.strip()))


def _pick_format(info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    is_live = bool(info.get("is_live"))
    candidates = []
    for f in info.get("formats") or []:
        url = f.get("url")
        if not url or f.get("vcodec") in (None, "none"):
            continue
        if f.get("protocol") in ("mhtml",):
            continue
        height = f.get("height") or 0
        proto = str(f.get("protocol") or "")
        is_hls = proto.startswith("m3u8")
        has_audio = f.get("acodec") not in (None, "none")
        within = 0 if (height and height <= MAX_HEIGHT) else 1
        # 라이브는 HLS 우선, 일반 영상은 직접 주소 우선
        proto_rank = (0 if is_hls else 1) if is_live else (1 if is_hls else 0)
        candidates.append(
            (within, proto_rank, 0 if has_audio else 1,
             -height if within == 0 else height, f)
        )
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[:4])
    return candidates[0][4]


def prepare_source(text: str) -> Tuple[str, Optional[dict]]:
    """유튜브 주소를 OpenCV가 읽을 수 있는 재생 주소로 바꿉니다."""
    url = text.strip()
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "ignore_no_formats_error": True,
        "socket_timeout": 20,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise RuntimeError(f"유튜브 주소를 열지 못했습니다: {exc}") from exc

    if not info:
        raise RuntimeError("유튜브 정보를 받지 못했습니다.")
    if info.get("live_status") == "is_upcoming":
        raise RuntimeError("아직 시작하지 않은 방송입니다.")

    chosen = _pick_format(info)
    if chosen is None:
        raise RuntimeError(
            "재생 가능한 영상 형식이 없습니다. 방송이 끝났거나 접근이 제한된 영상일 수 있습니다."
        )
    meta = {"title": info.get("title") or "", "is_live": bool(info.get("is_live"))}
    return chosen["url"], meta
