# news-image-20261124 — The World in One Day

[![news-image-20261124](https://make.fun/badge/news-image-20261124.svg)](https://make.fun/c/news-image-20261124/)
[![rank](https://make.fun/badge/news-image-20261124/WuYuanJie-211/news-image-20261124/rank.svg)](https://make.fun/c/news-image-20261124/)
[![reward](https://make.fun/badge/news-image-20261124/WuYuanJie-211/news-image-20261124/reward.svg)](https://make.fun/c/news-image-20261124/)

Sum up 24 November's world news in one image — a make.fun entry for
[news-image-20261124](https://make.fun/c/news-image-20261124/).
Bounty page: https://make.fun/bounty/news-image-20261124

One American-broadsheet front page, 1024×1024, pure flat-vector illustration
(zero photographs). v2 (round 2): strict Tuesday 24 November 2026 only —
37 stories, 13 illustrated heroes/cards, UTC timeline, numbers band,
numbered-pin world map, DATE CHECK audit. Research brief:
`../news-image-20261124-r2/rebuild-brief.md`.

## How it works

`main.py` (Python 3.13, standard library only) copies the repo-root
`entry.png` to `$MAKEFUN_OUTPUT_DIR/entry.png` (default `/output/entry.png`),
verifying the PNG header, IHDR/IEND CRCs, size (≤ 1 MiB) and dimensions
(exactly 1024×1024) first, then proving the copy deterministic: the source,
a staged temp copy, and the published file must all share one SHA-256.

## Files

- `entry.png` — the entry image (1024×1024, ≤ 1 MiB)
- `main.py` — the entry program
- `build/front.html` — the single-file source the front page was rendered from
- `.makefun/owner.json` — claim file (Solana payout wallet)
