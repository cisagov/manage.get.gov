def clean_txt_content(content: str) -> str:
    return content.strip()


def clean_cname_content(content: str) -> str:
    """Lowercase content for CNAME records, where the content is itself a
    hostname. Other record types (such as TXT) keep their original case."""
    return content.lower()
