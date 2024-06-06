import re


def parse_content_disposition(header_value):
    match = re.match(r"""form-data; (?P<parameters>.+)""", header_value)
    if match:
        parameters = match.groupdict()["parameters"]
        parsed_data = {}
        for param in parameters.split(";"):
            key, value = param.strip().split("=")
            parsed_data[key.strip('"')] = value.strip('"')
        return parsed_data
    raise ValueError(header_value)
