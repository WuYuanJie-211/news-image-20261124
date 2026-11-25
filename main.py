#!/usr/bin/env python3
"""Copy this folder's entry.png into the grader's output directory.

The grader sets MAKEFUN_OUTPUT_DIR and expects exactly one file there:
entry.png, 1024 by 1024 pixels, no larger than 1 MiB, readable by
whoever runs the checks.  The file is therefore written straight to
its final name (never staged through a temporary file, which would
leave it with restrictive permissions) and then chmodded to 0644.

After writing, the output is read back and compared byte for byte
with the source, so a silent short write cannot slip through.

Standard library only; no network, no extra files.
"""

import hashlib
import os
import struct
import sys
import zlib
from pathlib import Path

SIGNATURE = b"\x89PNG\r\n\x1a\n"
LIMIT = 1024 * 1024
SIDE = 1024


def die(text):
    print("error: " + text, file=sys.stderr)
    sys.exit(1)


def source_bytes():
    here = Path(__file__).resolve().parent
    src = here / "entry.png"
    try:
        blob = src.read_bytes()
    except OSError as err:
        die("cannot read entry.png beside main.py: %s" % err)
    if len(blob) == 0:
        die("source entry.png is empty")
    if len(blob) > LIMIT:
        die("source entry.png is %d bytes, over the 1 MiB limit" % len(blob))
    return src, blob


def crc_ok(kind, payload, stored):
    return (zlib.crc32(kind + payload) & 0xFFFFFFFF) == stored


def check_png(blob):
    if blob[:8] != SIGNATURE:
        die("bad PNG signature")
    if len(blob) < 33:
        die("file too short to hold an IHDR chunk")
    size = struct.unpack(">I", blob[8:12])[0]
    kind = blob[12:16]
    if kind != b"IHDR" or size != 13:
        die("first chunk is not a 13-byte IHDR")
    ihdr = blob[16:29]
    if not crc_ok(kind, ihdr, struct.unpack(">I", blob[29:33])[0]):
        die("IHDR chunk CRC mismatch")
    width, height = struct.unpack(">II", ihdr[:8])
    depth, colour, comp, filt, inter = ihdr[8], ihdr[9], ihdr[10], ihdr[11], ihdr[12]
    if (width, height) != (SIDE, SIDE):
        die("PNG is %dx%d, expected 1024x1024" % (width, height))
    if depth != 8:
        die("bit depth is %d, expected 8" % depth)
    if colour not in (2, 6):
        die("colour type is %d, expected 2 or 6" % colour)
    if comp != 0 or filt != 0:
        die("unexpected compression or filter method")
    if inter not in (0, 1):
        die("unexpected interlace method")
    pos = 33
    saw_data = False
    idat = bytearray()
    while True:
        if len(blob) - pos < 12:
            die("truncated chunk at offset %d" % pos)
        size = struct.unpack(">I", blob[pos:pos + 4])[0]
        kind = blob[pos + 4:pos + 8]
        end = pos + 12 + size
        if end > len(blob):
            die("chunk %r overruns the file" % kind)
        payload = blob[pos + 8:pos + 8 + size]
        stored = struct.unpack(">I", blob[pos + 8 + size:end])[0]
        if not crc_ok(kind, payload, stored):
            die("chunk %r CRC mismatch" % kind)
        if kind == b"IDAT":
            saw_data = True
            idat += payload
        if kind == b"IEND":
            if size != 0:
                die("IEND chunk carries data")
            if end != len(blob):
                die("bytes follow the IEND chunk")
            break
        pos = end
    if not saw_data:
        die("no IDAT chunk found")
    if inter == 0:
        # A CRC can pass while the compressed image data itself is broken,
        # so inflate it and check the scanline layout as well.
        channels = 3 if colour == 2 else 4
        want_len = SIDE * (1 + SIDE * channels)
        try:
            raw = zlib.decompress(bytes(idat))
        except zlib.error as err:
            die("IDAT data does not inflate: %s" % err)
        if len(raw) != want_len:
            die("inflated image is %d bytes, expected %d" % (len(raw), want_len))


def verify_output(dest, blob, want):
    """Re-read the written file and prove it is the same valid PNG.

    A hash match alone cannot catch a file that was truncated after
    the write, so the bytes are run through the full PNG structure
    check again instead of trusting the hash by itself.
    """
    back = dest.read_bytes()
    check_png(back)
    if hashlib.sha256(back).hexdigest() != want:
        die("output hash does not match the source")
    if len(back) != len(blob):
        die("output size does not match the source")
    return back


def target_path():
    raw = os.environ.get("MAKEFUN_OUTPUT_DIR")
    if not raw:
        die("MAKEFUN_OUTPUT_DIR is not set")
    folder = Path(raw)
    if folder.exists() and not folder.is_dir():
        die("MAKEFUN_OUTPUT_DIR %r is not a directory" % raw)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "entry.png"


def run():
    src, blob = source_bytes()
    check_png(blob)
    want = hashlib.sha256(blob).hexdigest()
    dest = target_path()
    if dest.resolve() == src.resolve():
        die("output path is the source file; refusing to overwrite it")
    with open(dest, "wb") as out:
        out.write(blob)
        out.flush()
        os.fsync(out.fileno())
    os.chmod(dest, 0o644)
    back = verify_output(dest, blob, want)
    mode = os.stat(dest).st_mode & 0o777
    if mode != 0o644:
        die("output mode is %03o, expected 644" % mode)
    print("wrote %s (%d bytes, sha256=%s, mode=0644, revalidated)" % (dest, len(blob), want))


if __name__ == "__main__":
    run()
