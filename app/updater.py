"""Check GitHub Releases for a newer Voxa build.

The check is intentionally manual and read-only: it only fetches metadata and
opens the download page. It never downloads or executes an installer itself.
"""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass, field
from typing import Any

GITHUB_REPO = "username-xusir/AI-Voice-Input"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"
USER_AGENT = "Voxa-UpdateCheck"


@dataclass
class ReleaseInfo:
    tag: str
    version: str
    name: str
    notes: str
    page_url: str
    published_at: str
    asset_name: str = ""
    asset_url: str = ""
    asset_size: int = 0
    asset_sha256: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


def _version_tuple(value: str) -> tuple[int, ...]:
    text = str(value).strip().lower()
    if text.startswith("v"):
        text = text[1:]
    match = re.match(r"(\d+(?:[._]\d+)*)", text)
    if not match:
        return ()
    return tuple(int(part) for part in re.split(r"[._]", match.group(1)))


def is_newer(latest: str, current: str) -> bool:
    a = _version_tuple(latest)
    b = _version_tuple(current)
    if not a:
        return False
    width = max(len(a), len(b))
    return a + (0,) * (width - len(a)) > b + (0,) * (width - len(b))


def _pick_installer(assets: list[dict[str, Any]]) -> dict[str, Any] | None:
    for asset in assets:
        name = str(asset.get("name", ""))
        if name.lower().startswith("voxa-setup-") and name.lower().endswith(".exe"):
            return asset
    for asset in assets:
        if str(asset.get("name", "")).lower().endswith(".exe"):
            return asset
    return None


def check_latest() -> ReleaseInfo:
    request = urllib.request.Request(
        GITHUB_API,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    tag = str(payload.get("tag_name") or "").strip()
    version = tag[1:] if tag.lower().startswith("v") else tag
    assets = payload.get("assets") or []
    installer = _pick_installer(assets) or {}
    digest = str(installer.get("digest") or "")
    sha256 = digest.removeprefix("sha256:") if digest.startswith("sha256:") else ""

    return ReleaseInfo(
        tag=tag,
        version=version,
        name=str(payload.get("name") or tag or "Voxa"),
        notes=str(payload.get("body") or ""),
        page_url=str(payload.get("html_url") or RELEASES_URL),
        published_at=str(payload.get("published_at") or ""),
        asset_name=str(installer.get("name") or ""),
        asset_url=str(installer.get("browser_download_url") or ""),
        asset_size=int(installer.get("size") or 0),
        asset_sha256=sha256,
        raw=payload,
    )
