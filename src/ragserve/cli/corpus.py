#!/usr/bin/env python3
"""Generate the bilingual review corpus: dozens of multi-page, mixed CN/EN PDFs.

This exists because a claim like "28 mixed CN/EN PDFs were ingested end to end" was once backed by
files a scratch script wrote into %TEMP% - unrepeatable by CI or by a reviewer, and gone the moment
the temp directory was cleaned. Evidence has to live in the repository (RULES.md R19), so the
generator is committed and deterministic: same seed, same corpus.

    python scripts/run.py --gen-corpus --out DIR [--count 36] [--seed 20261102]

What it produces, per document (3-5 sections, one page per section):

* `text`        - a normal multi-page document (English via WinAnsi, Chinese via a subset CJK font
                  with a ToUnicode CMap - the encoding real CJK PDFs actually ship);
* `mixed`       - the same, plus two image-only pages, so the document is partly unreadable but must
                  still be indexed;
* `pure image`  - no text layer at all, which the service must report as scanned rather than index.

It also writes `manifest.json` describing exactly what was generated, so a test can assert that
ingestion matches generation instead of trusting both ends independently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import zlib

IMAGE_WIDTH, IMAGE_HEIGHT = 220, 300

FAMILIES = ("handbook", "compliance", "techspec", "architecture")

TITLES = {
    "en": {"handbook": ["Employee Handbook", "Leave Policy", "Onboarding"],
           "compliance": ["Compliance Guide", "Data Protection", "Security Baseline"],
           "techspec": ["Technical Specification", "Ingestion Service", "API Reference"],
           "architecture": ["Architecture Overview", "Retrieval Design", "Storage Layout"]},
    "zh": {"handbook": ["员工手册", "年假制度", "入职指引"],
           "compliance": ["合规指引", "数据保护", "安全基线"],
           "techspec": ["技术规范", "接入服务", "接口说明"],
           "architecture": ["架构说明", "检索设计", "存储布局"]},
}

EN_SENTENCES = (
    "Full-time employees accrue {n} days of annual leave per calendar year.",
    "Unused leave may be carried over once, up to a maximum of five days.",
    "Requests above {n} MB are rejected with status 413 and a retry-after header.",
    "All staff must complete the annual data protection training within {n} days of joining.",
    "Sev-1 incidents must be acknowledged within {n} minutes and reviewed within five days.",
    "Passwords must be at least {n} characters and rotated every {n} months.",
    "The retrieval layer fuses BM25 with dense vectors before reranking.",
    "Audit logs are retained for {n} days and are immutable once written.",
    "Remote work is permitted for up to {n} days per week with written approval.",
    "Expenses above {n} USD require a receipt and manager approval.",
)

ZH_SENTENCES = (
    "全职员工每年可享受{n}天年假，未使用的年假最多可顺延五天。",
    "超过{n}兆字节的请求将被拒绝并返回状态码413。",
    "所有员工必须在入职{n}天内完成年度数据保护培训。",
    "一级事件必须在{n}分钟内确认，并在五个工作日内完成复盘。",
    "密码长度不得少于{n}个字符，每{n}个月必须更换一次。",
    "检索层将BM25与稠密向量结合，并在重排之前使用倒数排名融合。",
    "操作日志保留{n}天，写入后不可更改。",
    "每周最多可远程办公{n}天，且需要直属主管的书面批准。",
    "单笔超过{n}元的支出必须提供发票并经主管批准。",
)


# ---------------------------------------------------------------- PDF plumbing (stdlib only)

def _stream(body: bytes, compress: bool = True) -> bytes:
    if compress:
        data = zlib.compress(body)
        return b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(data) + data + b"\nendstream"
    return b"<< /Length %d >>\nstream\n" % len(body) + body + b"\nendstream"


def _build(objs: list) -> bytes:
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += (b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objs) + 1, xref))
    return bytes(out)


def _cmap(mapping: dict) -> str:
    lines = ["/CIDInit /ProcSet findresource begin", "12 dict begin", "begincmap",
             "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
             "/CMapName /Adobe-Identity-UCS def", "/CMapType 2 def",
             "1 begincodespacerange", "<0000> <FFFF>", "endcodespacerange",
             "%d beginbfchar" % len(mapping)]
    for cid, uni in sorted(mapping.items()):
        lines.append("<%04X> <%04X>" % (cid, uni))
    lines += ["endbfchar", "endcmap", "CMapName currentdict /CMap defineresource pop", "end", "end"]
    return "\n".join(lines)


def _write_pdf(path: str, pages: list, lang: str, rng: random.Random,
               seed: int, doc_index: int) -> None:
    """pages: list of (text | None). None means an image-only page."""
    objs: list = [b"<< /Type /Catalog /Pages 2 0 R >>", b"PLACEHOLDER"]
    if lang == "en":
        objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                    b"/Encoding /WinAnsiEncoding >>")
        base_resources = b"<< /Font << /F1 3 0 R >> >>"
    else:
        text = "\n".join(t for t in pages if t)
        seen, mapping, cid = {}, {}, 1
        for ch in text:
            if ch not in seen:
                seen[ch] = cid
                mapping[cid] = ord(ch)
                cid += 1
        objs.append(_stream(_cmap(mapping).encode("latin-1")))
        objs.append(b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light "
                    b"/CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 2 >> "
                    b"/FontDescriptor 6 0 R >>")
        objs.append(b"<< /Type /FontDescriptor /FontName /STSong-Light /Flags 4 "
                    b"/FontBBox [-25 -254 1000 880] /ItalicAngle 0 /Ascent 880 /Descent -254 "
                    b"/CapHeight 720 /StemV 58 >>")
        objs.append(b"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light "
                    b"/Encoding /Identity-H /DescendantFonts [5 0 R] /ToUnicode 4 0 R >>")
        base_resources = b"<< /Font << /F2 7 0 R >> >>"

    def encode(text: str) -> bytes:
        if lang == "en":
            escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
            return ("BT /F1 11 Tf 40 760 Td (%s) Tj ET" % escaped).encode("latin-1")
        return ("BT /F2 11 Tf 40 760 Td <%s> Tj ET"
                % "".join("%04X" % seen[ch] for ch in text)).encode("latin-1")

    page_specs = []  # (content object id, resources for that page)
    scanned_seen = 0
    for page in pages:
        if page is None:
            noise = _noise(seed, doc_index, scanned_seen, IMAGE_WIDTH * IMAGE_HEIGHT)
            page_specs.append(_scanned_page(objs, base_resources, noise))
            scanned_seen += 1
        else:
            objs.append(_stream(encode(page)))
            page_specs.append((len(objs), base_resources))
    page_ids = []
    for content_id, resources in page_specs:
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources "
                    + resources + b" /Contents %d 0 R >>" % content_id)
        page_ids.append(len(objs))
    objs[1] = (b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % p for p in page_ids)
               + b"] /Count %d >>" % len(page_ids))
    with open(path, "wb") as fh:
        fh.write(_build(objs))


# ---------------------------------------------------------------- corpus composition

def _section_body(rng: random.Random, lang: str) -> str:
    pool = EN_SENTENCES if lang == "en" else ZH_SENTENCES
    count = 7 + rng.randrange(3)  # 7-9 sentences
    return " ".join(rng.choice(pool).format(n=rng.choice((3, 5, 12, 30, 90, 180, 365)))
                    for _ in range(count))


def _noise(seed: int, doc_index: int, page_index: int, size: int) -> bytes:
    """Pseudo-noise for scan images, independent of Python version and of the content RNG.

    Two mistakes are deliberately avoided here. Drawing noise from the same `random.Random` that
    selects content made every later document depend on how many noise bytes came before it, and
    `randbytes` consumes a different amount of Mersenne Twister state across Python versions - the
    first CI run failed exactly there, on the first document after the first scanned page. And the
    noise itself must not vary either, so it is a SHA-256 counter stream: same seed, same bytes,
    on every platform and every Python.
    """
    out = bytearray()
    counter = 0
    while len(out) < size:
        block = hashlib.sha256(b"noise|%d|%d|%d|%d" % (seed, doc_index, page_index, counter)).digest()
        out += block
        counter += 1
    return bytes(out[:size])


def _scanned_page(objs: list, base_resources: bytes, noise: bytes) -> tuple:
    """An image-only page backed by real bitmap bytes.

    Real scanned PDFs are large because a scan *is* an image; a graphics operator alone is not one.
    The noise also exercises the loader's rule that an image XObject is never counted as a page:
    pseudo-random bytes are ~39% printable, far below the content-stream threshold.
    """
    objs.append(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d "
                b"/ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode >>\nstream\n"
                % (IMAGE_WIDTH, IMAGE_HEIGHT)
                + zlib.compress(noise) + b"\nendstream")
    image_id = len(objs)
    objs.append(_stream(b"q 460 0 0 596 76 90 cm /Im1 Do Q"))
    content_id = len(objs)
    return content_id, base_resources + b" /XObject << /Im1 %d 0 R >>" % image_id


def generate(out_dir: str, count: int, seed: int) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    rng = random.Random(seed)
    manifest = {"total": 0, "text_only": 0, "mixed": 0, "pure_image": 0, "en": 0, "zh": 0,
                "seed": seed, "count": count,
                "text_files": [], "mixed_files": [], "pure_image_files": []}

    for i in range(count):
        lang = "en" if i % 2 == 0 else "zh"
        if i % 6 == 5:
            kind = "pure_image"
        elif i % 6 == 3:
            kind = "mixed"
        else:
            kind = "text"
        family = FAMILIES[(i // 2) % len(FAMILIES)]
        title = TITLES[lang][family][i % 3]
        name = "%s-%s-%02d.pdf" % (family, lang, i)

        if kind == "pure_image":
            pages = [None] * (3 + rng.randrange(2))
            manifest["pure_image"] += 1
            manifest["pure_image_files"].append(name)
        else:
            sections = 4 + rng.randrange(3)  # 4-6 sections, one page each
            pages = ["%s\n%s" % (title, _section_body(rng, lang)) for _ in range(sections)]
            if kind == "mixed":
                pages += [None, None]
                manifest["mixed"] += 1
                manifest["mixed_files"].append(name)
            else:
                manifest["text_only"] += 1
                manifest["text_files"].append(name)
            manifest[lang] += 1

        _write_pdf(os.path.join(out_dir, name), pages, lang, rng, seed, i)
        manifest["total"] += 1

    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="directory to write the corpus into")
    parser.add_argument("--count", type=int, default=36, help="number of documents (default 36)")
    parser.add_argument("--seed", type=int, default=20261102, help="deterministic seed")
    args = parser.parse_args()
    manifest = generate(args.out, args.count, args.seed)
    print("wrote %d pdfs to %s" % (manifest["total"], args.out))
    print("  text_only %d | mixed %d | pure_image %d | en %d | zh %d"
          % (manifest["text_only"], manifest["mixed"], manifest["pure_image"],
             manifest["en"], manifest["zh"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
