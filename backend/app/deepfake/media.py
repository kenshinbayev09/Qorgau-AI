"""Media type detection by magic bytes (the client-declared MIME type is ignored)."""

from __future__ import annotations

from dataclasses import dataclass


class MediaError(Exception):
    def __init__(self, code: str, message: str = "", http_status: int = 422):
        super().__init__(message or code)
        self.code = code
        self.http_status = http_status


@dataclass(frozen=True)
class MediaFormat:
    kind: str  # "image" | "video"
    fmt: str


_VIDEO_BRANDS = {
    b"isom", b"iso2", b"iso4", b"iso5", b"iso6", b"mp41", b"mp42", b"avc1", b"M4V ", b"M4VP",
    b"qt  ", b"3gp4", b"3gp5", b"3gp6", b"3g2a", b"dash", b"MSNV", b"mmp4", b"f4v ",
}
_HEIF_BRANDS = {b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1", b"avif"}


def sniff(head: bytes) -> MediaFormat:
    """Return the actual media format or raise MediaError('unsupported_format')."""
    if len(head) < 12:
        raise MediaError("unsupported_format", "File too small to identify", 415)
    if head.startswith(b"\xff\xd8\xff"):
        return MediaFormat("image", "jpeg")
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return MediaFormat("image", "png")
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return MediaFormat("image", "webp")
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in _HEIF_BRANDS:
            raise MediaError("unsupported_format", "HEIC/AVIF is not supported; export as JPEG", 415)
        if brand in _VIDEO_BRANDS or brand.startswith(b"3g"):
            return MediaFormat("video", "mov" if brand == b"qt  " else "mp4")
        # unknown ISO-BMFF brand: let the decoder try, it is still a container format
        return MediaFormat("video", "mp4")
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return MediaFormat("video", "webm")
    if head[:4] == b"RIFF" and head[8:12] == b"AVI ":
        return MediaFormat("video", "avi")
    lowered = head[:256].lstrip().lower()
    if lowered.startswith((b"<!doctype html", b"<html", b"<head", b"<?xml")):
        raise MediaError("not_media_html", "This is a web page, not a media file", 415)
    raise MediaError("unsupported_format", "Unsupported or unrecognised file type", 415)
