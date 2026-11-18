import re
import unicodedata

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[ -]?)?(?:\(?\d{3}\)?[ -]?){1,2}\d{3,4}(?!\d)")
SSN_RE = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
OBFUSCATED_RE = re.compile(r"\b[A-Za-z0-9._%+-]+(?:\s*\[(?:at|dot)\]\s*)[A-Za-z0-9.-]+\b", re.I)
INJECTION_RE = re.compile(
    r"ignore\s+(?:all\s+)?(?:previous|prior|above)|system\s+prompt|jailbreak|bypass\s+(?:safety|policy)|"
    r"reveal\s+(?:secrets?|prompt|instructions)|act\s+as\s+(?:root|administrator)", re.I,
)


def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text).strip()


def redact_pii(text: str) -> tuple[str, bool]:
    redacted = OBFUSCATED_RE.sub("[REDACTED_EMAIL]", text)
    redacted = EMAIL_RE.sub("[REDACTED_EMAIL]", redacted)
    redacted = SSN_RE.sub("[REDACTED_SSN]", redacted)
    redacted = PHONE_RE.sub("[REDACTED_PHONE]", redacted)
    return redacted, redacted != text


def injection_detected(text: str) -> bool:
    normalized = unicodedata.normalize("NFKC", text).lower()
    return bool(INJECTION_RE.search(normalized))


def repair_argument(value: str) -> str:
    sku = re.fullmatch(r"SKU\s*(\d+)", value, re.I)
    if sku:
        return f"SKU-{int(sku.group(1)):03d}"
    lot = re.fullmatch(r"LOT\s*(\d+)", value, re.I)
    if lot:
        return f"LOT-{int(lot.group(1)):05d}"
    return value.strip()
