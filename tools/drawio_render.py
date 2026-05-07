#!/usr/bin/env python3
"""
Minimaler drawio -> SVG Renderer fuer /home/claude/architecture.drawio.

Versteht nur die in unserem Diagramm verwendeten Style-Attribute:
fillColor, strokeColor, dashed, fontSize, fontStyle (1=bold), rounded,
verticalAlign, align. Edges werden mit gerader Linie + Pfeilspitze gerendert
und am Box-Rand abgeschnitten. Container (Boxen, in denen andere Boxen liegen)
werden anhand ihrer Geometrie automatisch erkannt und zuerst gerendert,
damit innere Boxen darueber liegen.

Aufruf:
    python3 /home/claude/tools/drawio_render.py [input.drawio] [output.svg]
"""
from __future__ import annotations
import sys, html
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_INPUT = Path('/home/claude/architecture.drawio')
DEFAULT_OUTPUT = Path('/home/claude/architecture.svg')


def parse_style(s: str) -> dict[str, str]:
    return {k: v for k, v in (p.split('=', 1) for p in (s or '').split(';') if '=' in p)}


def line_rect_intersection(cx, cy, ox, oy, x, y, w, h):
    dx, dy = ox - cx, oy - cy
    if dx == 0 and dy == 0:
        return cx, cy
    cands = []
    if dx != 0:
        for ex in (x, x + w):
            t = (ex - cx) / dx
            if t > 0:
                ey = cy + t * dy
                if y <= ey <= y + h:
                    cands.append((t, ex, ey))
    if dy != 0:
        for ey in (y, y + h):
            t = (ey - cy) / dy
            if t > 0:
                ex = cx + t * dx
                if x <= ex <= x + w:
                    cands.append((t, ex, ey))
    if not cands:
        return cx, cy
    cands.sort()
    return cands[0][1], cands[0][2]


def is_container(v, others) -> bool:
    """Heuristik: Box A ist Container wenn mindestens 2 andere Boxen vollstaendig innen liegen."""
    inside = 0
    for o in others:
        if o is v:
            continue
        if v['x'] <= o['x'] and v['y'] <= o['y'] and \
           o['x'] + o['w'] <= v['x'] + v['w'] and o['y'] + o['h'] <= v['y'] + v['h']:
            inside += 1
            if inside >= 2:
                return True
    return False


def xml_escape(s: str) -> str:
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def render_text(x, y, w, h, text, style, parts):
    if not text:
        return
    font_size = float(style.get('fontSize', 12))
    bold = 'bold' if style.get('fontStyle') == '1' else 'normal'
    valign = style.get('verticalAlign', 'middle')
    halign = style.get('align', 'center')
    lines = text.split('\n')
    line_height = font_size * 1.25
    total_h = (len(lines) - 1) * line_height + font_size

    if valign == 'top':
        first_baseline = y + font_size + 4
    elif valign == 'bottom':
        first_baseline = y + h - total_h + font_size - 4
    else:
        first_baseline = y + (h - total_h) / 2 + font_size

    if halign == 'left':
        tx, anchor = x + 6, 'start'
    elif halign == 'right':
        tx, anchor = x + w - 6, 'end'
    else:
        tx, anchor = x + w / 2, 'middle'

    parts.append(
        f'<text x="{tx}" y="{first_baseline}" font-size="{font_size}" '
        f'font-weight="{bold}" text-anchor="{anchor}" fill="black">'
    )
    for i, line in enumerate(lines):
        esc = xml_escape(line)
        if i == 0:
            parts.append(f'<tspan x="{tx}">{esc}</tspan>')
        else:
            parts.append(f'<tspan x="{tx}" dy="{line_height}">{esc}</tspan>')
    parts.append('</text>')


def main() -> int:
    inp = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT

    tree = ET.parse(inp)
    cells = tree.findall('.//mxCell')

    vertices: dict[str, dict] = {}
    edges: list[dict] = []

    for c in cells:
        cid = c.get('id')
        style = parse_style(c.get('style', ''))
        if c.get('vertex') == '1':
            geom = c.find('mxGeometry')
            if geom is None:
                continue
            vertices[cid] = {
                'id': cid,
                'x': float(geom.get('x', 0)),
                'y': float(geom.get('y', 0)),
                'w': float(geom.get('width', 100)),
                'h': float(geom.get('height', 50)),
                'value': c.get('value', '') or '',
                'style': style,
            }
        elif c.get('edge') == '1':
            edges.append({
                'source': c.get('source'),
                'target': c.get('target'),
                'value': c.get('value', '') or '',
                'style': style,
            })

    gm = tree.getroot().find('.//mxGraphModel')
    pw = int(gm.get('pageWidth', 1400)) if gm is not None else 1400
    ph = int(gm.get('pageHeight', 1100)) if gm is not None else 1100

    # Container zuerst rendern (z-order)
    all_v = list(vertices.values())
    containers = [v for v in all_v if is_container(v, all_v)]
    inner = [v for v in all_v if v not in containers]
    ordered = containers + inner

    p: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {pw} {ph}" '
        f'width="{pw}" height="{ph}" font-family="Helvetica,Arial,sans-serif">',
        '<defs>',
        '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="8" markerHeight="8" orient="auto-start-reverse">',
        '<path d="M 0 0 L 10 5 L 0 10 Z" fill="#444"/>',
        '</marker>',
        '</defs>',
        '<rect width="100%" height="100%" fill="white"/>',
    ]

    for v in ordered:
        x, y, w, h = v['x'], v['y'], v['w'], v['h']
        s = v['style']
        fill = s.get('fillColor', 'white')
        stroke = s.get('strokeColor', 'black')
        rx = '8' if s.get('rounded') == '1' else '0'
        dash_attr = ' stroke-dasharray="4 4"' if s.get('dashed') == '1' else ''

        if fill.lower() == 'none' and stroke.lower() == 'none':
            pass
        elif stroke.lower() == 'none':
            p.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
                     f'rx="{rx}" ry="{rx}" fill="{fill}"/>')
        else:
            actual_fill = 'none' if fill.lower() == 'none' else fill
            p.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
                     f'rx="{rx}" ry="{rx}" fill="{actual_fill}" '
                     f'stroke="{stroke}" stroke-width="1.5"{dash_attr}/>')

        render_text(x, y, w, h, html.unescape(v['value']), s, p)

    for e in edges:
        sv = vertices.get(e['source'])
        tv = vertices.get(e['target'])
        if not sv or not tv:
            continue
        scx, scy = sv['x'] + sv['w'] / 2, sv['y'] + sv['h'] / 2
        tcx, tcy = tv['x'] + tv['w'] / 2, tv['y'] + tv['h'] / 2
        x1, y1 = line_rect_intersection(scx, scy, tcx, tcy, sv['x'], sv['y'], sv['w'], sv['h'])
        x2, y2 = line_rect_intersection(tcx, tcy, scx, scy, tv['x'], tv['y'], tv['w'], tv['h'])

        es = e['style']
        stroke = es.get('strokeColor', '#666')
        dash_attr = ' stroke-dasharray="4 4"' if es.get('dashed') == '1' else ''

        p.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                 f'stroke="{stroke}" stroke-width="1.3"{dash_attr} '
                 f'marker-end="url(#arrow)"/>')

        label = html.unescape(e['value']).strip()
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            font_size = float(es.get('fontSize', 9))
            esc = xml_escape(label)
            text_w = len(label) * font_size * 0.55
            p.append(f'<rect x="{mx - text_w / 2 - 3}" y="{my - font_size / 2 - 1}" '
                     f'width="{text_w + 6}" height="{font_size + 2}" '
                     f'fill="white" fill-opacity="0.9"/>')
            p.append(f'<text x="{mx}" y="{my + font_size / 3}" '
                     f'font-size="{font_size}" text-anchor="middle" '
                     f'fill="{stroke}">{esc}</text>')

    p.append('</svg>')
    out.write_text('\n'.join(p), encoding='utf-8')
    print(f'OK -> {out}  ({len(vertices)} Boxen, {len(edges)} Edges)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
