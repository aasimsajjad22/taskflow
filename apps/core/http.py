# hashlib: to turn our "version" text into a short fixed-length fingerprint.
import hashlib


# Build an ETag from the things that decide what a response contains.
# If ANY of the parts changes, the ETag changes.
def make_etag(*parts) -> str:
    # Join the parts into one text, e.g. "task|42|2026-10-15T13:41:43|3".
    raw = "|".join(str(part) for part in parts)
    # A short fingerprint of that text. The quotes are part of the HTTP ETag format.
    return '"' + hashlib.sha256(raw.encode()).hexdigest()[:32] + '"'


# Does the browser's If-None-Match header contain this ETag? (It can hold several, comma-separated.)
def etag_matches(request, etag: str) -> bool:
    # The header the browser sends back with the ETag it remembers ("" if none).
    header = request.headers.get("If-None-Match", "")
    # "*" means "any version"; otherwise compare each ETag in the list.
    return header.strip() == "*" or etag in [value.strip() for value in header.split(",")]
