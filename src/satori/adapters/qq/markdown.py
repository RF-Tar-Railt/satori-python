from satori.parser import Element


def extract_markdown_text(children: list[Element]):
    content = ""
    for child in children:
        if child.type == "text":
            text = str(child)
            while text.startswith("<markdown>"):
                text = text[10:]
            while text.endswith("</markdown>"):
                text = text[:-11]
            content += text
        elif child.type == "br":
            content += "\n"
        elif child.type == "p":
            if content and not content.endswith("\n"):
                content += "\n"
            content += extract_markdown_text(child.children)
            if content and not content.endswith("\n"):
                content += "\n"
        else:
            content += extract_markdown_text(child.children)
    return content
