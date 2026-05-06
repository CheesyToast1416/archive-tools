from __future__ import annotations

# Legacy CJK encodings tried when a password contains non-ASCII characters.
# Priority: most-common Chinese Windows encodings first, UTF-8 last.
CJK_ENCODINGS: list[str] = [
    "gbk",  # CP936 – dominant on Mainland Chinese Windows
    "gb2312",  # strict GBK subset; usually an alias of GBK
    "gb18030",  # superset of GBK used on newer Mainland systems
    "big5",  # Traditional Chinese – Taiwan / Hong Kong
    "big5hkscs",  # Hong Kong variant of BIG5
    "utf-8",  # Modern WinRAR ≥ 5.x / 7-Zip on any locale
]


def password_candidates(password: str) -> list[tuple[bytes, str]]:
    """
    Return a deduplicated list of ``(raw_bytes, encoding_name)`` pairs.

    Pure-ASCII passwords encode identically in every charset, so only one
    candidate is returned labelled ``"utf-8"`` (the universal superset).
    For non-ASCII passwords the full CJK legacy encoding list is tried.
    """
    # Fast path: ASCII passwords are the same in every encoding
    try:
        raw = password.encode("ascii")
        return [(raw, "utf-8")]
    except UnicodeEncodeError:
        pass

    seen: set[bytes] = set()
    result: list[tuple[bytes, str]] = []
    for enc in CJK_ENCODINGS:
        try:
            raw = password.encode(enc)
        except (UnicodeEncodeError, LookupError):
            continue
        if raw not in seen:
            seen.add(raw)
            result.append((raw, enc))
    return result
