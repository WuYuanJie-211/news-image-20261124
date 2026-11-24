#!/usr/bin/env python3
"""news-image-20261124 entry program (v1).

Takes the repository's entry.png (a 1024x1024 PNG, at most 1 MiB) and
places a verified copy at $MAKEFUN_OUTPUT_DIR/entry.png (or
/output/entry.png when the variable is unset). Standard library only,
no network access. The PNG is rejected unless it is structurally
complete: correct signature, an IHDR with matching CRC and the wanted
dimensions, a full chunk walk with valid CRCs, at least one IDAT, and
an IEND that ends exactly at the end of the file.
"""

import hashlib
import os
import sys
import zlib
from pathlib import Path

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
LIMIT_BYTES = 1_048_576
WANTED = (1024, 1024)
FALLBACK_DIR = "/output"


def fail(message):
    print(f"entry.png rejected: {message}", file=sys.stderr)
    return 1


def read_source():
    root = Path(__file__).resolve().parent
    blob = (root / "entry.png").read_bytes()
    if len(blob) > LIMIT_BYTES:
        raise ValueError(f"{len(blob)} bytes, over the 1 MiB limit")
    if len(blob) < 8 or blob[:8] != PNG_MAGIC:
        raise ValueError("bad PNG signature")
    return blob


def ihdr_size(blob):
    """Pull (width, height) out of the IHDR chunk, checking its CRC.

    Also validates the IHDR's own fields: the render is a true-colour
    8-bit image, so bit depth must be 8, colour type 2 (RGB) or 6
    (RGBA), compression and filter methods 0, and interlace 0 or 1.
    A PNG with any other combination is not the image this entry
    ships, so it is rejected rather than copied.
    """
    if len(blob) < 33 or blob[12:16] != b"IHDR":
        raise ValueError("first chunk is not IHDR")
    stored = int.from_bytes(blob[29:33], "big")
    if zlib.crc32(blob[12:29]) & 0xFFFFFFFF != stored:
        raise ValueError("IHDR CRC mismatch")
    width = int.from_bytes(blob[16:20], "big")
    height = int.from_bytes(blob[20:24], "big")
    if (width, height) != WANTED:
        raise ValueError(f"{width}x{height}, must be 1024x1024")
    bit_depth, colour_type = blob[24], blob[25]
    compression, filter_method, interlace = blob[26], blob[27], blob[28]
    if bit_depth != 8:
        raise ValueError(f"bit depth {bit_depth}, must be 8")
    if colour_type not in (2, 6):
        raise ValueError(f"colour type {colour_type}, must be 2 or 6")
    if compression != 0 or filter_method != 0 or interlace not in (0, 1):
        raise ValueError("unsupported compression/filter/interlace fields")
    return width, height


def walk_chunks(blob):
    """Scan every chunk end to end; return True only for a whole PNG.

    Each chunk's declared length must stay inside the file, each stored
    CRC must match the bytes it covers, at least one IDAT must appear,
    and the walk must stop exactly at the file end right after IEND.
    Anything else means the image is truncated, padded, or corrupt.
    """
    cursor = 8
    saw_data = False
    while cursor + 8 <= len(blob):
        size = int.from_bytes(blob[cursor:cursor + 4], "big")
        kind = blob[cursor + 4:cursor + 8]
        stop = cursor + 12 + size
        if stop > len(blob):
            return False
        check = int.from_bytes(blob[stop - 4:stop], "big")
        if zlib.crc32(blob[cursor + 4:stop - 4]) & 0xFFFFFFFF != check:
            return False
        if kind == b"IDAT":
            saw_data = True
        if kind == b"IEND":
            return saw_data and stop == len(blob)
        cursor = stop
    return False


def run():
    try:
        blob = read_source()
        width, height = ihdr_size(blob)
    except (OSError, ValueError) as problem:
        return fail(str(problem))
    if not walk_chunks(blob):
        return fail("chunk walk failed (bad length/CRC, no IDAT, "
                     "missing IEND, or trailing bytes)")
    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", FALLBACK_DIR))
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "entry.png"
    target.write_bytes(blob)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    if digest != hashlib.sha256(blob).hexdigest():
        return fail("copy does not match the source (sha256)")
    print(f"wrote {target} ({len(blob)} bytes, {width}x{height}, "
          f"sha256 {digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
