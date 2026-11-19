def clean_txt_content(content: str) -> str:
    return content.strip()


def clean_hostname_content(content: str) -> str:
    """Lowercase hostname content for CNAME, MX, and PTR records.
    Other record types (such as TXT) keep their original case."""
    return content.lower()
