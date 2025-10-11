"""
Name: fleep.py
Description: File format determination library
Author: Mykyta Paliienko
License: MIT
"""

# fmt: off

data = [
    {"type": "raster-image", "extension": "bmp", "mime": "image/bmp", "offset": 0, "signature": ["42 4D"]},
    {"type": "raster-image", "extension": "gif", "mime": "image/gif", "offset": 0, "signature": ["47 49 46 38"]},
    {"type": "raster-image", "extension": "jpg", "mime": "image/jpeg", "offset": 0, "signature": ["FF D8 FF"]},
    {"type": "raster-image", "extension": "jp2", "mime": "image/jp2", "offset": 0, "signature": ["00 00 00 0C 6A 50 20 20"]},
    {"type": "raster-image", "extension": "png", "mime": "image/png", "offset": 0, "signature": ["89 50 4E 47 0D 0A 1A 0A"]},
    {"type": "raster-image", "extension": "webp", "mime": "image/webp", "offset": 8, "signature": ["57 45 42 50"]},
    {"type": "raster-image", "extension": "ico", "mime": "image/x-icon", "offset": 0, "signature": ["00 00 01 00"]},
    {"type": "raster-image", "extension": "psd", "mime": "image/vnd.adobe.photoshop", "offset": 0, "signature": ["38 42 50 53"]},
    {"type": "raster-image", "extension": "tiff", "mime": "image/tiff", "offset": 0, "signature": ["49 20 49", "49 49 2A 00", "4D 4D 00 2A", "4D 4D 00 2B"]},
    {"type": "raw-image", "extension": "raw", "mime": "application/octet-stream", "offset": 0, "signature": ["49 49 55 00"]},
    {"type": "raw-image", "extension": "arw", "mime": "application/octet-stream", "offset": 0, "signature": ["49 49 2A 00"]},
    {"type": "raw-image", "extension": "x3f", "mime": "application/octet-stream", "offset": 0, "signature": ["46 4F 56 62"]},
    {"type": "raw-image", "extension": "srw", "mime": "application/octet-stream", "offset": 0, "signature": ["4D 4D 00 2A"]},
    {"type": "raw-image", "extension": "pef", "mime": "application/octet-stream", "offset": 0, "signature": ["4D 4D 00 2A"]},
    {"type": "raw-image", "extension": "rw2", "mime": "application/octet-stream", "offset": 0, "signature": ["49 49 55 00"]},
    {"type": "raw-image", "extension": "nef", "mime": "application/octet-stream", "offset": 0, "signature": ["4D 4D 00 2A"]},
    {"type": "raw-image", "extension": "nrw", "mime": "application/octet-stream", "offset": 0, "signature": ["49 49 2A 00"]},
    {"type": "raw-image", "extension": "raf", "mime": "application/octet-stream", "offset": 0, "signature": ["46 55 4A 49"]},
    {"type": "raw-image", "extension": "erf", "mime": "application/octet-stream", "offset": 0, "signature": ["4D 4D 00 2A"]},
    {"type": "raw-image", "extension": "crw", "mime": "application/octet-stream", "offset": 0, "signature": ["49 49 1A 00"]},
    {"type": "raw-image", "extension": "cr2", "mime": "application/octet-stream", "offset": 0, "signature": ["49 49 2A 00"]},
    {"type": "raw-image", "extension": "orf", "mime": "application/octet-stream", "offset": 0, "signature": ["49 49 52 4F", "49 49 52 53"]},
    {"type": "raw-image", "extension": "dng", "mime": "application/octet-stream", "offset": 0, "signature": ["4D 4D 00 2A", "49 49 2A 00"]},
    {"type": "vector-image", "extension": "ai", "mime": "application/postscript", "offset": 0, "signature": ["25 50 44 46"]},
    {"type": "vector-image", "extension": "eps", "mime": "application/postscript", "offset": 0, "signature": ["C5 D0 D3 C6", "25 21 50 53 2D 41 64 6F"]},
    {"type": "3d-image", "extension": "obj", "mime": "text/plain", "offset": 2, "signature": ["4D 61 78 32 4F 62 6A", "42 6C 65 6E 64 65 72"]},
    {"type": "3d-image", "extension": "mtl", "mime": "text/plain", "offset": 2, "signature": ["4D 61 78 32 4D 74 6C", "42 6C 65 6E 64 65 72 20 4D 54 4C 20 46 69 6C 65"]},
    {"type": "3d-image", "extension": "xsi", "mime": "text/plain", "offset": 0, "signature": ["78 73 69"]},
    {"type": "3d-image", "extension": "ply", "mime": "text/plain", "offset": 50, "signature": ["70 6C 79"]},
    {"type": "3d-image", "extension": "ma", "mime": "text/plain", "offset": 2, "signature": ["4D 61 79 61"]},
    {"type": "3d-image", "extension": "wrl", "mime": "text/plain", "offset": 1, "signature": ["56 52 4D 4C"]},
    {"type": "3d-image", "extension": "x3d", "mime": "application/xml", "offset": 50, "signature": ["58 33 44"]},
    {"type": "3d-image", "extension": "fbx", "mime": "application/octet-stream", "offset": 2, "signature": ["46 42 58"]},
    {"type": "3d-image", "extension": "ms3d", "mime": "application/octet-stream", "offset": 0, "signature": ["4D 53 33 44"]},
    {"type": "3d-image", "extension": "c4d", "mime": "application/octet-stream", "offset": 0, "signature": ["58 43 34 44 43 34 44 36"]},
    {"type": "audio", "extension": "aiff", "mime": "audio/aiff", "offset": 0, "signature": ["46 4F 52 4D 00"]},
    {"type": "audio", "extension": "aac", "mime": "audio/aac", "offset": 0, "signature": ["FF F1", "FF F9"]},
    {"type": "audio", "extension": "midi", "mime": "audio/midi", "offset": 0, "signature": ["4D 54 68 64"]},
    {"type": "audio", "extension": "mp3", "mime": "audio/mpeg", "offset": 0, "signature": ["49 44 33", "FF FB"]},
    {"type": "audio", "extension": "m4a", "mime": "audio/mp4", "offset": 4, "signature": ["66 74 79 70 4D 34 41 20"]},
    {"type": "audio", "extension": "oga", "mime": "audio/ogg", "offset": 0, "signature": ["4F 67 67 53 00 02 00 00"]},
    {"type": "audio", "extension": "wav", "mime": "audio/wav", "offset": 0, "signature": ["52 49 46 46"]},
    {"type": "audio", "extension": "wma", "mime": "audio/x-ms-wma", "offset": 0, "signature": ["30 26 B2 75 8E 66 CF 11"]},
    {"type": "audio", "extension": "flac", "mime": "audio/flac", "offset": 0, "signature": ["66 4C 61 43 00 00 00 22"]},
    {"type": "audio", "extension": "mka", "mime": "audio/x-matroska", "offset": 31, "signature": ["6D 61 74 72 6F 73 6B 61"]},
    {"type": "audio", "extension": "au", "mime": "audio/basic", "offset": 0, "signature": ["2E 73 6E 64"]},
    {"type": "audio", "extension": "ra", "mime": "application/octet-stream", "offset": 0, "signature": ["2E 52 4D 46"]},
    {"type": "audio", "extension": "amr", "mime": "application/octet-stream", "offset": 0, "signature": ["23 21 41 4D"]},
    {"type": "audio", "extension": "ac3", "mime": "application/octet-stream", "offset": 0, "signature": ["0B 77"]},
    {"type": "audio", "extension": "voc", "mime": "application/octet-stream", "offset": 0, "signature": ["43 72 65 61 74 69 76 65"]},
    {"type": "video", "extension": "3g2", "mime": "video/3gpp2", "offset": 4, "signature": ["66 74 79 70 33 67 70"]},
    {"type": "video", "extension": "3gp", "mime": "video/3gpp", "offset": 4, "signature": ["66 74 79 70 33 67 70"]},
    {"type": "video", "extension": "avi", "mime": "video/avi", "offset": 8, "signature": ["41 56 49 20 4C 49 53 54"]},
    {"type": "video", "extension": "flv", "mime": "video/x-flv", "offset": 0, "signature": ["46 4C 56"]},
    {"type": "video", "extension": "mxf", "mime": "application/mxf", "offset": 0, "signature": ["06 0E 2B 34"]},
    {"type": "video", "extension": "m4v", "mime": "video/mp4", "offset": 4, "signature": ["66 74 79 70 4D 34 56 20", "66 74 79 70 6D 70 34 32"]},
    {"type": "video", "extension": "mkv", "mime": "video/x-matroska", "offset": 31, "signature": ["6D 61 74 72 6F 73 6B 61"]},
    {"type": "video", "extension": "mov", "mime": "video/quicktime", "offset": 4, "signature": ["66 74 79 70 71 74 20 20", "6D 6F 6F 76", "66 72 65 65", "6D 64 61 74", "77 69 64 65", "70 6E 6F 74", "73 6B 69 70"]},
    {"type": "video", "extension": "mp4", "mime": "video/mp4", "offset": 4, "signature": ["66 74 79 70 4D 53 4E 56", "66 74 79 70 69 73 6F 6D"]},
    {"type": "video", "extension": "swf", "mime": "application/vnd.adobe.flash-movie", "offset": 0, "signature": ["43 57 53", "46 57 53"]},
    {"type": "video", "extension": "mpg", "mime": "video/mpeg", "offset": 0, "signature": ["00 00 01 BA"]},
    {"type": "video", "extension": "vob", "mime": "video/dvd", "offset": 0, "signature": ["00 00 01 BA"]},
    {"type": "video", "extension": "wmv", "mime": "video/x-ms-wmv", "offset": 0, "signature": ["30 26 B2 75 8E 66 CF 11"]},
    {"type": "video", "extension": "asf", "mime": "video/x-ms-asf", "offset": 0, "signature": ["30 26 B2 75 8E 66 CF 11"]},
    {"type": "video", "extension": "ogv", "mime": "video/ogg", "offset": 0, "signature": ["4F 67 67 53 00 02 00 00"]},
    {"type": "video", "extension": "webm", "mime": "video/webm", "offset": 0, "signature": ["1A 45 DF A3"]},
    {"type": "document", "extension": "odt", "mime": "application/vnd.oasis.opendocument.text", "offset": 73, "signature": ["74 65 78 74"]},
    {"type": "document", "extension": "odp", "mime": "application/vnd.oasis.opendocument.presentation", "offset": 73, "signature": ["70 72 65 73 65 6E 74 61 74 69 6F 6E"]},
    {"type": "document", "extension": "ods", "mime": "application/vnd.oasis.opendocument.spreadsheet", "offset": 73, "signature": ["73 70 72 65 61 64 73 68 65 65 74"]},
    {"type": "document", "extension": "doc", "mime": "application/vnd.ms-excel", "offset": 0, "signature": ["D0 CF 11 E0 A1 B1 1A E1", "50 4B 03 04 14 00 06 00"]},
    {"type": "document", "extension": "pps", "mime": "application/vnd.ms-powerpoint", "offset": 0, "signature": ["D0 CF 11 E0 A1 B1 1A E1", "50 4B 03 04 14 00 06 00"]},
    {"type": "document", "extension": "ppt", "mime": "application/vnd.ms-powerpoint", "offset": 0, "signature": ["D0 CF 11 E0 A1 B1 1A E1", "50 4B 03 04 14 00 06 00"]},
    {"type": "document", "extension": "xls", "mime": "application/vnd.ms-excel", "offset": 0, "signature": ["D0 CF 11 E0 A1 B1 1A E1", "50 4B 03 04 14 00 06 00"]},
    {"type": "document", "extension": "docx", "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "offset": 0, "signature": ["D0 CF 11 E0 A1 B1 1A E1", "50 4B 03 04 14 00 06 00"]},
    {"type": "document", "extension": "pptx", "mime": "application/vnd.openxmlformats-officedocument.presentationml.presentation", "offset": 0, "signature": ["D0 CF 11 E0 A1 B1 1A E1", "50 4B 03 04 14 00 06 00"]},
    {"type": "document", "extension": "xlsx", "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "offset": 0, "signature": ["D0 CF 11 E0 A1 B1 1A E1", "50 4B 03 04 14 00 06 00"]},
    {"type": "document", "extension": "pages", "mime": "application/zip", "offset": 0, "signature": ["50 4B 03 04"]},
    {"type": "document", "extension": "key", "mime": "application/zip", "offset": 0, "signature": ["50 4B 03 04"]},
    {"type": "document", "extension": "numbers", "mime": "application/zip", "offset": 0, "signature": ["50 4B 03 04"]},
    {"type": "document", "extension": "pdf", "mime": "application/pdf", "offset": 0, "signature": ["25 50 44 46"]},
    {"type": "document", "extension": "rtf", "mime": "application/rtf", "offset": 0, "signature": ["7B 5C 72 74 66 31"]},
    {"type": "document", "extension": "epub", "mime": "application/epub+zip", "offset": 0, "signature": ["50 4B 03 04"]},
    {"type": "document", "extension": "xml", "mime": "application/xml", "offset": 2, "signature": ["78 6D 6C"]},
    {"type": "archive", "extension": "7z", "mime": "application/x-7z-compressed", "offset": 0, "signature": ["37 7A BC AF 27 1C"]},
    {"type": "archive", "extension": "rar", "mime": "application/vnd.rar", "offset": 0, "signature": ["52 61 72 21 1A 07 00", "52 61 72 21 1A 07 01 00"]},
    {"type": "archive", "extension": "tar.z", "mime": "application/x-compress", "offset": 0, "signature": ["1F 9D", "1F A0"]},
    {"type": "archive", "extension": "gz", "mime": "application/gzip", "offset": 0, "signature": ["1F 8B 08"]},
    {"type": "archive", "extension": "zip", "mime": "application/zip", "offset": 0, "signature": ["50 4B 03 04", "50 4B 05 06", "50 4B 07 08"]},
    {"type": "archive", "extension": "dmg", "mime": "application/x-apple-diskimage", "offset": 0, "signature": ["78 01 73 0D 62 62 60"]},
    {"type": "archive", "extension": "iso", "mime": "application/octet-stream", "offset": 0, "signature": ["43 49 53 4F", "43 44 30 30 31"]},
    {"type": "executable", "extension": "com", "mime": "application/x-msdownload", "offset": 0, "signature": ["4D 5A"]},
    {"type": "executable", "extension": "exe", "mime": "application/vnd.microsoft.portable-executable", "offset": 0, "signature": ["4D 5A 90 00"]},
    {"type": "executable", "extension": "jar", "mime": "application/java-archive", "offset": 0, "signature": ["50 4B 03 04"]},
    {"type": "font", "extension": "ttf", "mime": "font/ttf", "offset": 0, "signature": ["00 01 00 00"]},
    {"type": "font", "extension": "otf", "mime": "font/otf", "offset": 0, "signature": ["4F 54 54 4F"]},
    {"type": "font", "extension": "woff", "mime": "font/woff", "offset": 0, "signature": ["77 4F 46 46"]},
    {"type": "font", "extension": "woff2", "mime": "font/woff2", "offset": 0, "signature": ["77 4F 46 32"]},
    {"type": "system", "extension": "cab", "mime": "application/vnd.ms-cab-compressed", "offset": 0, "signature": ["4D 53 43 46"]},
    {"type": "system", "extension": "cat", "mime": "application/vnd.microsoft.portable-executable", "offset": 0, "signature": ["30 82"]},
    {"type": "system", "extension": "dll", "mime": "application/vnd.microsoft.portable-executable", "offset": 0, "signature": ["4D 5A 90 00"]},
    {"type": "system", "extension": "drv", "mime": "application/vnd.microsoft.portable-executable", "offset": 0, "signature": ["4D 5A 90 00"]},
    {"type": "system", "extension": "sdb", "mime": "application/vnd.microsoft.portable-executable", "offset": 8, "signature": ["73 64 62 66"]},
    {"type": "system", "extension": "sys", "mime": "application/vnd.microsoft.portable-executable", "offset": 0, "signature": ["4D 5A 80 00", "4D 5A 90 00"]},
    {"type": "system", "extension": "reg", "mime": "application/vnd.microsoft.portable-executable", "offset": 0, "signature": ["52 45 47 45 44 49 54", "57 69 6E 64 6F 77 73 20 52 65 67 69 73 74 72 79"]},
    {"type": "database", "extension": "sqlite", "mime": "application/x-sqlite3", "offset": 0, "signature": ["53 51 4C 69 74 65 20 66 6F 72 6D 61 74 20 33 00"]}
]

# fmt: on


class Info:
    """
    Generates object with given arguments

    Args:
        types (list) -> list of file types
        extensions (list) -> list of file extensions
        mimes (list) -> list of file MIME types

    Returns:
        (<class 'fleep.Info'>) -> Class instance
    """

    def __init__(self, types: list, extensions: list, mimes: list):
        self.types = types
        self.extensions = extensions
        self.mimes = mimes

    def type_matches(self, type_: str):
        """Checks if file type matches with given type"""
        return type_ in self.types

    def extension_matches(self, extension: str):
        """Checks if file extension matches with given extension"""
        return extension in self.extensions

    def mime_matches(self, mime: str):
        """Checks if file MIME type matches with given MIME type"""
        return mime in self.mimes


def get(obj: bytes):
    """
    Determines file format and picks suitable file types, extensions and MIME types

    Args:
        obj (bytes) -> byte sequence (128 bytes are enough)

    Returns:
        (<class 'fleep.Info'>) -> Class instance
    """

    if not isinstance(obj, bytes):
        raise TypeError("object type must be bytes")

    stream = " ".join([f"{byte:02X}" for byte in obj])

    types = {}
    extensions = {}
    mimes = {}
    for element in data:
        for signature in element["signature"]:
            offset = element["offset"] * 2 + element["offset"]
            if signature == stream[offset : len(signature) + offset]:
                types[element["type"]] = len(signature)
                extensions[element["extension"]] = len(signature)
                mimes[element["mime"]] = len(signature)
    return Info(
        sorted(types, key=lambda x: types.get(x, False), reverse=True),
        sorted(extensions.keys(), key=lambda x: extensions.get(x, False), reverse=True),
        sorted(mimes.keys(), key=lambda x: mimes.get(x, False), reverse=True),
    )


def supported_types():
    """Returns a list of supported file types"""
    return sorted({x["type"] for x in data})


def supported_extensions():
    """Returns a list of supported file extensions"""
    return sorted({x["extension"] for x in data})


def supported_mimes():
    """Returns a list of supported file MIME types"""
    return sorted({x["mime"] for x in data})
