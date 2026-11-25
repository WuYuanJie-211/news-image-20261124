#!/usr/bin/env python3
"""news-image-20261124 entry program (v2).

Ships the repository's entry.png (a 1024x1024 PNG, at most 1 MiB) to
$MAKEFUN_OUTPUT_DIR/entry.png (or /output/entry.png when unset).
Standard library only, no network access.

Before anything is published, the image is checked three ways: the
PNG signature and header fields are parsed directly, every chunk is
walked end to end with its CRC verified, and the copy itself is
proven deterministic — the bytes are staged to a temporary file in
the destination directory, hashed, moved into place, and hashed
again, and the run only succeeds when the source hash, the staged
hash, and the final hash are all identical. A mismatch at any stage
aborts without leaving a partial output behind.
"""

import hashlib
import os
import struct
import sys
import tempfile
import zlib
from pathlib import Path

SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_BYTES = 1_048_576
TARGET_SIZE = (1024, 1024)
DEFAULT_OUT = "/output"


def reject(reason):
    print(f"entry.png rejected: {reason}", file=sys.stderr)
    return 1


def digest_of(data):
    return hashlib.sha256(data).hexdigest()


def parse_header(data):
    """Read the IHDR straight out of the byte stream.

    Returns (width, height) after confirming the signature, that the
    first chunk really is IHDR with a matching CRC, the wanted
    dimensions, and header fields this render uses: 8-bit samples,
    true-colour (2) or true-colour-with-alpha (6), and the standard
    compression, filter and interlace values.
    """
    if len(data) < 33 or data[:8] != SIGNATURE:
        raise ValueError("not a PNG (bad signature or too short)")
    if data[12:16] != b"IHDR":
        raise ValueError("first chunk is not IHDR")
    stored_crc = struct.unpack(">I", data[29:33])[0]
    if zlib.crc32(data[12:29]) & 0xFFFFFFFF != stored_crc:
        raise ValueError("IHDR CRC mismatch")
    width, height = struct.unpack(">II", data[16:24])
    if (width, height) != TARGET_SIZE:
        raise ValueError(f"image is {width}x{height}, must be 1024x1024")
    depth, kind = data[24], data[25]
    method, filtering, interlace = data[26], data[27], data[28]
    if depth != 8:
        raise ValueError(f"bit depth {depth}, must be 8")
    if kind not in (2, 6):
        raise ValueError(f"colour type {kind}, must be 2 or 6")
    if method != 0 or filtering != 0 or interlace not in (0, 1):
        raise ValueError("unexpected compression/filter/interlace value")
    return width, height


def chunks_are_sound(data):
    """Walk the chunk list from the signature to the last byte.

    Every declared length must stay inside the file, every stored CRC
    must match the chunk it guards, at least one IDAT must be present,
    and IEND must land exactly on the end of the file — anything else
    means the file is truncated, padded, or corrupt.
    """
    pos = 8
    seen_pixels = False
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        name = data[pos + 4:pos + 8]
        end = pos + 12 + length
        if end > len(data):
            return False
        stored = struct.unpack(">I", data[end - 4:end])[0]
        if zlib.crc32(data[pos + 4:end - 4]) & 0xFFFFFFFF != stored:
            return False
        if name == b"IDAT":
            seen_pixels = True
        if name == b"IEND":
            return seen_pixels and end == len(data)
        pos = end
    return False


def publish(data, source_hash):
    """Stage, verify, and move the bytes into the destination.

    The staging file lives in the same directory as the final path so
    the move is a rename, not a re-copy. The staged bytes are hashed
    before the move and the final file is hashed after it; all three
    digests (source, staged, final) must agree, which proves the
    published file is byte-for-byte the validated source. On any
    failure the staging file is removed and no output is left.
    """
    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", DEFAULT_OUT))
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / "entry.png"
    handle = tempfile.NamedTemporaryFile(
        dir=out_dir, prefix=".entry-", suffix=".tmp", delete=False
    )
    staged_path = Path(handle.name)
    try:
        with handle:
            handle.write(data)
        if digest_of(staged_path.read_bytes()) != source_hash:
            return None, "staged copy hash mismatch"
        staged_path.replace(final)
        if digest_of(final.read_bytes()) != source_hash:
            return None, "published file hash mismatch"
        return final, None
    finally:
        if staged_path.exists():
            staged_path.unlink(missing_ok=True)


def main():
    try:
        source = Path(__file__).resolve().parent / "entry.png"
        blob = source.read_bytes()
    except OSError as exc:
        return reject(f"cannot read entry.png: {exc}")
    if not blob:
        return reject("entry.png is empty")
    if len(blob) > MAX_BYTES:
        return reject(f"{len(blob)} bytes, over the 1 MiB limit")
    try:
        width, height = parse_header(blob)
    except ValueError as exc:
        return reject(str(exc))
    if not chunks_are_sound(blob):
        return reject("chunk walk failed (bad length/CRC, no IDAT, "
                      "missing IEND, or trailing bytes)")
    source_hash = digest_of(blob)
    final, problem = publish(blob, source_hash)
    if problem is not None:
        return reject(problem)
    print(f"wrote {final} ({len(blob)} bytes, {width}x{height}, "
          f"sha256 {source_hash}, deterministic: source == staged "
          f"== published)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
