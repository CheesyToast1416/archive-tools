from __future__ import annotations

# Fallback encoding list for non-ASCII passwords.
# Most-common East-Asian Windows codepages first; UTF-8 last as the catch-all.
# Extend this list to support additional regional encodings.
PASSWORD_ENCODINGS: list[str] = [
    "gbk",  # CP936 — dominant on Mainland Chinese Windows
    "gb2312",  # strict GBK subset; usually an alias of GBK
    "gb18030",  # superset of GBK, full Unicode coverage
    "big5",  # Traditional Chinese — Taiwan / Hong Kong
    "big5hkscs",  # Hong Kong variant of Big5
    "utf-8",  # modern WinRAR ≥ 5 / 7-Zip on any locale
]


def password_candidates(password: str) -> list[tuple[bytes, str]]:
    """
    Return a deduplicated list of ``(raw_bytes, encoding_name)`` pairs to
    try when matching an archive password whose on-disk encoding is unknown.

    Pure-ASCII passwords encode identically in every charset, so only one
    candidate labelled ``"utf-8"`` is returned (ASCII is a subset of UTF-8).
    For non-ASCII passwords every encoding in :data:`PASSWORD_ENCODINGS` is
    attempted and duplicate byte sequences are suppressed.
    """
    # Fast path: ASCII is the same in every encoding.
    try:
        raw = password.encode("ascii")
        return [(raw, "utf-8")]
    except UnicodeEncodeError:
        pass

    seen: set[bytes] = set()
    result: list[tuple[bytes, str]] = []
    for enc in PASSWORD_ENCODINGS:
        try:
            raw = password.encode(enc)
        except (UnicodeEncodeError, LookupError):
            continue
        if raw not in seen:
            seen.add(raw)
            result.append((raw, enc))
    return result
