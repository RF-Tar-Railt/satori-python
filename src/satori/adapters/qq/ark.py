from satori.parser import Element


def create_payload(ark):
    return {
        "msg_type": 3,
        "content": " ",
        "ark": ark,
    }


def parse_ark_kv(item):
    if not isinstance(item, dict) or not (key := item.get("key")) or not isinstance(key, str):
        return
    value = item.get("value")
    if isinstance(value, str):
        return {"key": key, "value": value}
    if not isinstance(value, list):
        return
    obj = []
    for v in value:
        if not isinstance(v, dict) or not isinstance(v.get("obj_kv"), list):
            continue
        obj_kv = []
        for kv in v["obj_kv"]:
            if not isinstance(kv, dict) or not (k := kv.get("key")) or not isinstance(k, str):
                continue
            obj_kv.append({"key": k, "value": kv.get("value")})
        obj.append({"obj_kv": obj_kv})
    if not obj:
        return
    return {"key": key, "obj": obj}


def parse_ark(value):
    if not isinstance(value, dict) or not value:
        return
    kvlist = value.get("kv")
    if not isinstance(kvlist, list) or not kvlist:
        return
    kv = []
    for item in kvlist:
        if not (parsed := parse_ark_kv(item)):
            continue
        kv.append(parsed)
    if not kv:
        return
    return {
        "template_id": value.get("template_id"),
        "kv": kv,
    }


def parse_ark_generic(attrs: dict):
    source = attrs["content"] if "content" in attrs and isinstance(attrs["content"], dict) else attrs.get("ark")
    ark = parse_ark(source)
    if not ark:
        return
    return create_payload(ark)


def extract_text(children: list[Element]):
    content = ""
    for child in children:
        if child.type == "text":
            content += str(child)
        elif child.type == "br":
            content += "\n"
        else:
            content += extract_text(child.children)
    return content


def _parse_text_field(source: dict, key: str):
    value = source.get(key)
    return value if isinstance(value, str) else None


def parse_ark24(attrs: dict, children: list[Element]):
    source = attrs["content"] if "content" in attrs and isinstance(attrs["content"], dict) else attrs
    desc = _parse_text_field(source, "desc")
    prompt = _parse_text_field(source, "prompt")
    title = _parse_text_field(source, "title")
    meta_desc = _parse_text_field(source, "meta_desc") or _parse_text_field(source, "metaDesc")
    img = _parse_text_field(source, "img")
    link = _parse_text_field(source, "link")
    subtitle = _parse_text_field(source, "subtitle") or _parse_text_field(source, "subTitle")
    if any(field is None for field in [desc, prompt, title, meta_desc, img, link, subtitle]):
        return
    return create_payload(
        {
            "template_id": 24,
            "kv": [
                {"key": "#DESC#", "value": desc},
                {"key": "#PROMPT#", "value": prompt},
                {"key": "#TITLE#", "value": title},
                {"key": "#METADESC#", "value": meta_desc},
                {"key": "#IMG#", "value": img},
                {"key": "#LINK#", "value": link},
                {"key": "#SUBTITLE#", "value": subtitle},
            ],
        }
    )


def parse_ark37(attrs: dict, children: list[Element]):
    source = attrs["content"] if "content" in attrs and isinstance(attrs["content"], dict) else attrs
    prompt = _parse_text_field(source, "prompt")
    title = (
        _parse_text_field(source, "metatitle")
        or _parse_text_field(source, "metaTitle")
        or _parse_text_field(source, "title")
    )
    subtitle = (
        _parse_text_field(source, "metasubtitle")
        or _parse_text_field(source, "metasubTitle")
        or _parse_text_field(source, "subtitle")
    )
    cover = (
        _parse_text_field(source, "metacover")
        or _parse_text_field(source, "metaCover")
        or _parse_text_field(source, "cover")
    )
    url = (
        _parse_text_field(source, "metaurl")
        or _parse_text_field(source, "metaUrl")
        or _parse_text_field(source, "url")
        or extract_text(children)
    )
    if any(field is None for field in [prompt, title, subtitle, cover, url]):
        return
    return create_payload(
        {
            "template_id": 37,
            "kv": [
                {"key": "#PROMPT#", "value": prompt},
                {"key": "#METATITLE#", "value": title},
                {"key": "#METASUBTITLE#", "value": subtitle},
                {"key": "#METACOVER#", "value": cover},
                {"key": "#METAURL#", "value": url},
            ],
        }
    )


def parse_ark23(attrs: dict, children: list[Element]):
    source = attrs["content"] if "content" in attrs and isinstance(attrs["content"], dict) else attrs
    desc = _parse_text_field(source, "desc")
    prompt = _parse_text_field(source, "prompt")
    list_source = source.get("list")
    if not isinstance(list_source, list):
        return
    list_ = []
    for item in list_source:
        if not isinstance(item, dict):
            continue
        _desc = _parse_text_field(item, "desc")
        if not _desc:
            continue
        obj_kv = [{"key": "desc", "value": _desc}]
        link = _parse_text_field(item, "link")
        if link:
            obj_kv.append({"key": "link", "value": link})
        list_.append({"obj_kv": obj_kv})
    if any(not field for field in [desc, prompt, list_]):
        return
    return create_payload(
        {
            "template_id": 23,
            "kv": [
                {"key": "#DESC#", "value": desc},
                {"key": "#PROMPT#", "value": prompt},
                {"key": "#LIST#", "obj": list_},
            ],
        }
    )


def parse_qq_ark(element: Element):
    type_, attrs, children = element.type, element.attrs, element.children
    if type_ == "qq:ark23":
        return parse_ark23(attrs, children)
    if type_ == "qq:ark24":
        return parse_ark24(attrs, children)
    if type_ == "qq:ark37":
        return parse_ark37(attrs, children)
    if type_ == "qq:ark":
        return parse_ark_generic(attrs)
