from base64 import b64decode

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7


def aes_ecb_encrypt(plaintext: bytes, key: bytes) -> bytes:
    padder = PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    encryptor = cipher.encryptor()
    return encryptor.update(padded) + encryptor.finalize()


def aes_ecb_decrypt(ciphertext: bytes, key: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def calculate_ciphertext_size(plaintext_size: int) -> int:
    return ((plaintext_size // 16) + 1) * 16


def parse_aes_key(aes_key_base64: str) -> bytes:
    decoded = b64decode(aes_key_base64)
    if len(decoded) == 16:
        return decoded
    if len(decoded) == 32:
        try:
            value = decoded.decode("ascii")
            if all(char in "0123456789abcdefABCDEF" for char in value):
                return bytes.fromhex(value)
        except (UnicodeDecodeError, ValueError):
            pass
    raise ValueError(f"aes_key must decode to 16 raw bytes or 32-char hex string, got {len(decoded)} bytes")
