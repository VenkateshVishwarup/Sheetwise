"""Conservative field classification. No uploaded values are sent to the model."""
import re

SECRET = re.compile(r'token|password|secret|api[_ .-]?key|authorization|credential', re.I)
PERSONAL = re.compile(r'email|phone|mobile|caller|contact|full.?name|user.?name|latitude|longitude|pincode|address|symptom|condition|summary|last_query|last_input|content|\blat\b|\blng\b|\blong\b', re.I)
IDENTIFIER = re.compile(r'(^id$|[_. ]id$|^id[_. ]|bsuid|hashed|ackid)', re.I)
EMAIL = re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}')
PHONE = re.compile(r'(?<!\w)\+?\d[\d ()-]{8,}\d(?!\w)')


def mask_text(value: str) -> str:
    value = EMAIL.sub('[email removed]', value)
    value = re.sub(r'(?:sk-|Bearer )[A-Za-z0-9_-]{12,}', '[secret removed]', value)
    return PHONE.sub('[number removed]', value)


def field_privacy(name: str, samples: list[str]) -> tuple[bool, str]:
    if IDENTIFIER.search(name):
        return True, 'identifier'
    if PERSONAL.search(name):
        return True, 'personal'
    if any(EMAIL.search(v) or (PHONE.fullmatch(v) and not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v)) or v.startswith(('http://', 'https://')) for v in samples):
        return True, 'personal'
    if any(len(v) > 160 or v.startswith(('{', '[')) for v in samples):
        return True, 'unstructured'
    return False, ''
