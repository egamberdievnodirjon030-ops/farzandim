"""Jadvalli Word (.docx) hujjat — tashqi kutubxonasiz (OOXML): sarlavha, ma'lumot qatorlari, jadval (sarlavha qatori
har sahifada takrorlanadi), oxirida imzo qatorlari. A4, Times New Roman — rasmiy ro'yxatlar uchun.
"""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from xml.sax.saxutils import escape

_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
A4_W, A4_H = 11906, 16838
MARGIN = {"top": 1134, "bottom": 1134, "left": 1418, "right": 851}


def usable_width(landscape: bool = False) -> int:
    return (A4_H if landscape else A4_W) - MARGIN["left"] - MARGIN["right"]


def _run(text: str, bold: bool = False, size: int = 24, italic: bool = False) -> str:
    props = ("<w:b/>" if bold else "") + ("<w:i/>" if italic else "") + f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    parts = str(text).split("\n")
    body = '<w:br/>'.join(f'<w:t xml:space="preserve">{escape(p)}</w:t>' for p in parts)
    return f"<w:r><w:rPr>{props}</w:rPr>{body}</w:r>"


def _para(runs: str, align: str = "left", after: int = 0, before: int = 0, keep: bool = False) -> str:
    return (f'<w:p><w:pPr>{"<w:keepNext/>" if keep else ""}<w:spacing w:before="{before}" w:after="{after}" w:line="240" '
            f'w:lineRule="auto"/><w:jc w:val="{align}"/></w:pPr>{runs}</w:p>')


def _cell(text: str, width: int, bold: bool = False, shade: bool = False, align: str = "left", size: int = 21) -> str:
    sh = '<w:shd w:val="clear" w:color="auto" w:fill="E7ECF3"/>' if shade else ""
    return (f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{sh}<w:vAlign w:val="center"/></w:tcPr>'
            f'{_para(_run(text, bold, size), align)}</w:tc>')


def build(title: str, info: list[tuple[str, str]], columns: list[tuple[str, int, str]], rows: list[list[str]],
          footer: list[str] | None = None, top: str = "", landscape: bool = False, row_height: int = 0) -> bytes:
    """columns: (sarlavha, kenglik ulushi, tekislash: left | center | right); kengliklar sahifaga moslanadi.
    row_height — qator balandligi (twip, eng kami; imzo ustuni bo'lsa ~420)."""
    total = usable_width(landscape)
    share = sum(c[1] for c in columns) or 1
    widths = [max(400, total * c[1] // share) for c in columns]
    border = "".join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
                     for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    head = ('<w:tr><w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>'
            + "".join(_cell(c[0], w, bold=True, shade=True, align="center") for c, w in zip(columns, widths)) + "</w:tr>")
    trh = f'<w:trHeight w:val="{row_height}"/>' if row_height else ""
    body = "".join(f'<w:tr><w:trPr><w:cantSplit/>{trh}</w:trPr>'
                   + "".join(_cell(v if v is not None else "", w, align=c[2]) for v, c, w in zip(r, columns, widths))
                   + "</w:tr>" for r in rows)
    table = (f'<w:tbl><w:tblPr><w:tblW w:w="{sum(widths)}" w:type="dxa"/><w:tblBorders>{border}</w:tblBorders>'
             f'<w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/>'
             f'</w:tblCellMar></w:tblPr><w:tblGrid>{grid}</w:tblGrid>{head}{body}</w:tbl>')
    parts = []
    if top:
        parts.append(_para(_run(top.upper(), bold=True, size=24), "center", after=120))
    parts.append(_para(_run(title, bold=True, size=28), "center", after=200))
    for k, v in info:
        parts.append(_para(_run(f"{k}: ", bold=True) + _run(v), "left", after=40))
    parts.append(_para("", after=120))
    parts.append(table)
    for i, line in enumerate(footer or []):
        parts.append(_para(_run(line), "left", before=360 if i == 0 else 120))
    w, h = (A4_H, A4_W) if landscape else (A4_W, A4_H)
    orient = ' w:orient="landscape"' if landscape else ""
    sect = (f'<w:sectPr><w:pgSz w:w="{w}" w:h="{h}"{orient}/>'
            f'<w:pgMar w:top="{MARGIN["top"]}" w:right="{MARGIN["right"]}" w:bottom="{MARGIN["bottom"]}" '
            f'w:left="{MARGIN["left"]}" w:header="709" w:footer="709" w:gutter="0"/></w:sectPr>')
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {_W}><w:body>{"".join(parts)}{sect}'
           f'</w:body></w:document>')
    styles = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {_W}><w:docDefaults><w:rPrDefault><w:rPr>'
              '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman" w:eastAsia="Times New Roman"/>'
              '<w:sz w:val="24"/><w:szCs w:val="24"/><w:lang w:val="uz-Latn-UZ"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>'
              '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults></w:styles>')
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>',
        "word/_rels/document.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        "word/document.xml": doc,
        "word/styles.xml": styles,
        "docProps/core.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f'<dc:title>{escape(title)}</dc:title><dc:creator>JIDU</dc:creator>'
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created></cp:coreProperties>',
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()
