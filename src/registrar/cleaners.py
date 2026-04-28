def clean_txt_content(content: str) -> str:
    """Clean the content field for TXT records to ensure it is enclosed in quotes."""
    if content and not (content.startswith('"') and content.endswith('"')):
        content = f'"{content}"'
    return content
