#!/usr/bin/env python3
"""Write the verified news front-page PNG to the grader output folder.

The program reads entry.png from its own directory, validates the PNG
structure, writes those exact bytes to $MAKEFUN_OUTPUT_DIR/entry.png
and then forces the output file mode to 0644, so a checker running
under a different identity in the grading sandbox can read it.

Only the Python standard library is used. Nothing is written anywhere
except the single output file, and no network access is made.
"""

import hashlib
import os
import struct
import sys
import zlib
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_BYTES = 1024 * 1024
EXPECTED_WIDTH = 1024
EXPECTED_HEIGHT = 1024


def fail(message):
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_source():
    source = Path(__file__).resolve().parent / "entry.png"
    try:
        data = source.read_bytes()
    except OSError as exc:
        fail(f"cannot read source entry.png next to main.py: {exc}")
    if not data:
        fail("source entry.png is empty")
    if len(data) > MAX_BYTES:
        fail(f"source entry.png is {len(data)} bytes, over the 1 MiB limit")
    return source, data


def check_chunk_crc(chunk_type, chunk_data, stored_crc, where):
    actual = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
    if actual != stored_crc:
        fail(f"{where}: bad CRC for chunk {chunk_type!r}")


def validate_png(data):
    if data[:8] != PNG_SIGNATURE:
        fail("bad PNG signature")
    if len(data) < 8 + 25:  # signature + smallest possible IHDR chunk
        fail("file too short for an IHDR chunk")
    offset = 8
    length = struct.unpack(">I", data[offset:offset + 4])[0]
    chunk_type = data[offset + 4:offset + 8]
    if chunk_type != b"IHDR":
        fail("first chunk is not IHDR")
    if length != 13:
        fail(f"IHDR length is {length}, expected 13")
    ihdr = data[offset + 8:offset + 21]
    stored = struct.unpack(">I", data[offset + 21:offset + 25])[0]
    check_chunk_crc(chunk_type, ihdr, stored, "IHDR")
    width, height = struct.unpack(">II", ihdr[0:8])
    bit_depth = ihdr[8]
    color_type = ihdr[9]
    compression = ihdr[10]
    filter_method = ihdr[11]
    interlace = ihdr[12]
    if (width, height) != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
        fail(f"IHDR size is {width}x{height}, expected 1024x1024")
    if bit_depth != 8:
        fail(f"bit depth is {bit_depth}, expected 8")
    if color_type not in (2, 6):
        fail(f"color type is {color_type}, expected 2 or 6")
    if compression != 0:
        fail(f"compression method is {compression}, expected 0")
    if filter_method != 0:
        fail(f"filter method is {filter_method}, expected 0")
    if interlace not in (0, 1):
        fail(f"interlace method is {interlace}, expected 0 or 1")
    offset += 25
    seen_idat = False
    seen_iend = False
    while offset < len(data):
        if len(data) - offset < 12:
            fail("truncated chunk header")
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(data):
            fail(f"chunk {chunk_type!r} overruns the file")
        chunk_data = data[offset + 8:offset + 8 + length]
        stored = struct.unpack(">I", data[offset + 8 + length:end])[0]
        check_chunk_crc(chunk_type, chunk_data, stored, f"chunk at {offset}")
        if chunk_type == b"IDAT":
            seen_idat = True
        if chunk_type == b"IEND":
            if length != 0:
                fail("IEND chunk carries data")
            if end != len(data):
                fail("bytes follow the IEND chunk")
            seen_iend = True
            offset = end
            break
        offset = end
    if not seen_idat:
        fail("no IDAT chunk found")
    if not seen_iend:
        fail("no IEND chunk found")
    if offset != len(data):
        fail("trailing bytes after IEND")


def output_path():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR")
    if not out_dir:
        fail("MAKEFUN_OUTPUT_DIR is not set")
    out_dir_path = Path(out_dir)
    if out_dir_path.exists() and not out_dir_path.is_dir():
        fail(f"MAKEFUN_OUTPUT_DIR {out_dir!r} is not a directory")
    out_dir_path.mkdir(parents=True, exist_ok=True)
    return out_dir_path / "entry.png"


def main():
    source, data = read_source()
    validate_png(data)
    digest = hashlib.sha256(data).hexdigest()
    target = output_path()
    if target.resolve() == source.resolve():
        fail("output path is the source file; refusing to overwrite it")
    # Direct write: no temporary file is staged in the output directory,
    # so the finished entry.png never inherits tempfile's 0600 mode.
    with open(target, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(target, 0o644)
    written = target.read_bytes()
    if hashlib.sha256(written).hexdigest() != digest:
        fail("output hash does not match the source")
    if len(written) != len(data):
        fail("output size does not match the source")
    mode = os.stat(target).st_mode & 0o777
    if mode != 0o644:
        fail(f"output mode is {mode:03o}, expected 644")
    print(f"wrote {target} ({len(data)} bytes, sha256={digest}, mode=0644)")


if __name__ == "__main__":
    main()
