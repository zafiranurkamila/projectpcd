from __future__ import annotations

import numpy as np

# -------------------------------------------------
# LZW compressor / decompressor for raw image data
# -------------------------------------------------
# The algorithm works on a *byte stream*.  We convert the
# NumPy image (height x width x channels) to raw bytes,
# compress those bytes with classic LZW, and later rebuild the
# original array using the stored shape.
# -------------------------------------------------

def _to_bytes(data: np.ndarray) -> bytes:
    """Convert an image array to a flat ``bytes`` object.
    The image is assumed to be ``uint8`` (standard OpenCV output).
    """
    return data.tobytes()

def _from_bytes(b: bytes, shape: tuple[int, int, int]) -> np.ndarray:
    """Re‑create the original ``uint8`` image from raw bytes.
    ``shape`` is a 3‑tuple ``(height, width, channels)``.
    """
    arr = np.frombuffer(b, dtype=np.uint8)
    return arr.reshape(shape)

# ------------------------------------------------------------------
# LZW compression – returns a list of integer codes (each fits in 2 B)
# ------------------------------------------------------------------
def compress_image(image: np.ndarray) -> list[int]:
    """Compress a ``uint8`` image (H×W×C) using LZW.
    The output is a list of integer codes; each code will be stored
    as 2 bytes (big‑endian) by the caller.
    """
    raw = _to_bytes(image)
    # Initialise dictionary with all possible single‑byte symbols
    dict_size = 256
    dictionary = {bytes([i]): i for i in range(dict_size)}

    w = b""
    result: list[int] = []
    for k in raw:
        wk = w + bytes([k])
        if wk in dictionary:
            w = wk
        else:
            result.append(dictionary[w])
            # Add new entry to the dictionary
            dictionary[wk] = dict_size
            dict_size += 1
            w = bytes([k])
    # Output the code for the last w
    if w:
        result.append(dictionary[w])
    return result

# ------------------------------------------------------------------
# LZW decompression – restores the original byte stream
# ------------------------------------------------------------------
def decompress_image(codes: list[int], shape: tuple[int, int, int]) -> np.ndarray:
    """Decompress a list of LZW codes back to the original image.
    ``shape`` must match the original ``(height, width, channels)``.
    """
    # Initialise dictionary with single‑byte entries
    dict_size = 256
    dictionary = {i: bytes([i]) for i in range(dict_size)}

    result_bytes = bytearray()
    prev_code = codes[0]
    prev_entry = dictionary[prev_code]
    result_bytes.extend(prev_entry)

    for code in codes[1:]:
        if code in dictionary:
            entry = dictionary[code]
        elif code == dict_size:
            # Special case: code = dict_size => entry = prev_entry + first char of prev_entry
            entry = prev_entry + prev_entry[:1]
        else:
            raise ValueError("Bad LZW code: {}".format(code))

        result_bytes.extend(entry)

        # Add new entry to the dictionary
        dictionary[dict_size] = prev_entry + entry[:1]
        dict_size += 1
        prev_entry = entry

    # Convert bytes back to NumPy array with the given shape
    return _from_bytes(bytes(result_bytes), shape)

# ------------------------------------------------------------------
# Variable‑bit packing for LZW codes
# ------------------------------------------------------------------
from typing import List
import math

def pack_codes(codes: List[int]) -> bytes:
    """Pack a list of integer LZW codes into a compact bit‑stream.
    The function uses the smallest number of bits that can represent the
    maximum code value, but never fewer than 9 bits (the classic LZW start).
    Returns a ``bytes`` object ready to be written to a file.

    Format: [4‑byte big‑endian code count] + [packed bit‑stream]
    """
    if not codes:
        return b""
    max_code = max(codes)
    bits = max(9, max_code.bit_length())
    # Ensure bits does not exceed 16 (our codes fit in 16 bits)
    bits = min(bits, 16)
    bit_buffer = 0
    bit_len = 0
    out = bytearray()
    # Write the number of codes first so unpack can truncate padding
    out.extend(len(codes).to_bytes(4, byteorder='big'))
    for code in codes:
        bit_buffer = (bit_buffer << bits) | code
        bit_len += bits
        while bit_len >= 8:
            bit_len -= 8
            out.append((bit_buffer >> bit_len) & 0xFF)
    if bit_len > 0:
        # Pad the remaining bits with zeros on the right
        out.append((bit_buffer << (8 - bit_len)) & 0xFF)
    return bytes(out)

def unpack_codes(data: bytes, bits: int) -> List[int]:
    """Reverse of :func:`pack_codes` – read a bit‑stream into integer codes.
    ``bits`` must be the same width that was used during packing.

    The first 4 bytes of *data* encode the number of codes (big‑endian)
    so that trailing padding bits are discarded.
    """
    if bits < 1:
        raise ValueError("bits must be positive")
    # Read the code count header written by pack_codes
    num_codes = int.from_bytes(data[:4], byteorder='big')
    data = data[4:]  # remaining is the actual bit‑stream
    bit_buffer = 0
    bit_len = 0
    codes: List[int] = []
    for b in data:
        bit_buffer = (bit_buffer << 8) | b
        bit_len += 8
        while bit_len >= bits:
            bit_len -= bits
            codes.append((bit_buffer >> bit_len) & ((1 << bits) - 1))
            if len(codes) == num_codes:
                return codes
    return codes
