"""
Security utilities:
- sanitize_html: strips dangerous tags/attributes from Quill HTML output
- validate_file_magic: checks actual file bytes, not just extension
"""
import re
import os

# ── HTML sanitisation ─────────────────────────────────────────────────────────
# Allowed tags and their allowed attributes (whitelist approach)
_ALLOWED_TAGS = {
    'p', 'br', 'strong', 'em', 'u', 's', 'h1', 'h2', 'h3', 'h4',
    'ul', 'ol', 'li', 'blockquote', 'a', 'img', 'span', 'div',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
}
_ALLOWED_ATTRS = {
    'a': {'href', 'title', 'target', 'rel'},
    'img': {'src', 'alt', 'width', 'height'},
    '*': {'class'},
}
# Dangerous protocols in href/src
_BAD_PROTOCOLS = re.compile(r'^(javascript|vbscript|data):', re.IGNORECASE)


def sanitize_html(raw_html: str) -> str:
    """
    Lightweight HTML sanitiser — no external deps.
    Strips script/style/iframe tags and javascript: hrefs.
    For production with heavy user content, consider bleach or nh3.
    """
    if not raw_html:
        return ''
    # Remove script, style, iframe, object, embed entirely (including content)
    cleaned = re.sub(
        r'<(script|style|iframe|object|embed|form|input|button|select|textarea)'
        r'[\s\S]*?</\1>',
        '', raw_html, flags=re.IGNORECASE
    )
    # Remove self-closing dangerous tags
    cleaned = re.sub(
        r'<(script|style|iframe|object|embed|link|meta|base)[^>]*/?>',
        '', cleaned, flags=re.IGNORECASE
    )
    # Strip on* event handlers from any tag
    cleaned = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+on\w+\s*=\s*\S+', '', cleaned, flags=re.IGNORECASE)
    # Strip javascript: / vbscript: / data: from href and src
    def _clean_attr(m):
        attr = m.group(0)
        if _BAD_PROTOCOLS.search(m.group(1)):
            return ''
        return attr
    cleaned = re.sub(r'(?:href|src)\s*=\s*["\']([^"\']*)["\']', _clean_attr, cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


# ── Magic-byte file validation ────────────────────────────────────────────────
_MAGIC = {
    b'\xff\xd8\xff':           'image/jpeg',
    b'\x89PNG\r\n\x1a\n':     'image/png',
    b'GIF87a':                 'image/gif',
    b'GIF89a':                 'image/gif',
    b'RIFF':                   'image/webp',   # checked further below
    b'%PDF':                   'application/pdf',
    b'\xd0\xcf\x11\xe0':      'application/msword',   # .doc
    b'PK\x03\x04':            'application/zip',       # .docx / .xlsx
}

_ALLOWED_MIME_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'application/pdf', 'application/msword',
    'application/zip',   # covers .docx
    'image/svg+xml',     # SVG — text-based, handled separately
}


def validate_file_magic(file_storage) -> bool:
    """
    Read the first 16 bytes of an uploaded file and check against known magic bytes.
    Returns True if the file type is allowed, False otherwise.
    Resets the stream position after reading.
    """
    header = file_storage.stream.read(16)
    file_storage.stream.seek(0)

    if not header:
        return False

    # SVG is XML text — check for <svg tag
    if b'<svg' in header.lower() or b'<?xml' in header:
        return True

    for magic, mime in _MAGIC.items():
        if header.startswith(magic):
            if mime == 'image/webp':
                # RIFF....WEBP
                return len(header) >= 12 and header[8:12] == b'WEBP'
            return mime in _ALLOWED_MIME_TYPES

    return False
