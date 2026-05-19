#!/usr/bin/env python3
"""Markdown -> HTML 단일 파일 변환기.

KSAdmin top.html 의 md2html 위젯(skin/basic/js/md2html.js)을 Python 단일 코드로 포팅했다.
10가지 컨셉 테마(인라인 CSS 프리셋)를 지원하며, 입력 .md 파일과 같은 디렉토리에 .html 파일을 생성한다.

지원 문법:
  - ATX 헤딩(# ~ ######), Setext 헤딩(===, ---)
  - 단락, 하드 라인브레이크(트레일링 공백 2개 또는 백슬래시)
  - 굵게(**, __), 기울임(*, _), 인라인 코드(`), 취소선(~~)
  - 링크 [text](url "title"), 오토링크 <url>, 이미지 ![alt](src "title")
  - 순서 없는/있는 리스트(들여쓰기 중첩)
  - 인용(>) 중첩
  - 펜스 코드블록(``` 또는 ~~~)과 들여쓰기 코드블록
  - 가로줄(---, ***, ___), 파이프 표(:---:, ---:, :---)

지원 테마(--theme 인자, 기본값: meeting):
  white / dark / release / meeting / report / proposal / manual / notice / plan / quotation
한글 별칭도 지원: White, Dark, 릴리즈노트, 회의록, 업무보고, 제안서, 매뉴얼, 공지사항, 기획안, 견적서
"""
from __future__ import annotations

import argparse
import html
import os
import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# --------------------------- 인라인 파싱 ---------------------------

_ESCAPABLE = set(r"\`*_{}[]()#+-.!>~|")


def _escape_html(text: str) -> str:
	return (
		text.replace("&", "&amp;")
		.replace("<", "&lt;")
		.replace(">", "&gt;")
		.replace('"', "&quot;")
	)


def _process_backslash_escapes(text: str) -> str:
	out = []
	i = 0
	while i < len(text):
		ch = text[i]
		if ch == "\\" and i + 1 < len(text) and text[i + 1] in _ESCAPABLE:
			out.append(text[i + 1])
			i += 2
		else:
			out.append(ch)
			i += 1
	return "".join(out)


_INLINE_CODE_RE = re.compile(r"(`+)([^`]|[^`].*?[^`])\1(?!`)", re.DOTALL)
_IMAGE_RE = re.compile(
	r"!\[(?P<alt>(?:\\.|[^\]\\])*)\]\((?P<src>\S*?)(?:\s+\"(?P<title>(?:\\.|[^\"\\])*)\")?\)"
)
_LINK_RE = re.compile(
	r"\[(?P<text>(?:\\.|[^\]\\])*)\]\((?P<url>\S*?)(?:\s+\"(?P<title>(?:\\.|[^\"\\])*)\")?\)"
)
_AUTOLINK_RE = re.compile(r"<((?:https?|ftp)://[^\s<>]+|[^\s<>@]+@[^\s<>]+)>")
_STRONG_RE = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", re.DOTALL)
_EM_RE = re.compile(r"(?<![\\*_\w])([*_])(?=\S)(.+?)(?<=\S)\1(?!\w)", re.DOTALL)
_STRIKE_RE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~", re.DOTALL)
_HARDBREAK_RE = re.compile(r"(?:  +|\\)\n")
_RAW_HTML_RE = re.compile(r"<!--[\s\S]*?-->|</?[a-zA-Z][^<>]*>")


def _placeholder(token: str, idx: int) -> str:
	return f"\x00{token}{idx}\x00"


def render_inline(text: str) -> str:
	"""인라인 마크다운을 HTML로 변환한다."""
	placeholders: List[str] = []

	def store(html_fragment: str) -> str:
		placeholders.append(html_fragment)
		return _placeholder("INL", len(placeholders) - 1)

	# 1) 인라인 코드 (내부 추가 처리 안 함)
	def code_repl(m: re.Match) -> str:
		content = m.group(2).strip()
		return store(f"<code>{_escape_html(content)}</code>")

	text = _INLINE_CODE_RE.sub(code_repl, text)

	# 1-1) raw 인라인 HTML 태그 placeholder (escape 단계 영향 회피)
	text = _RAW_HTML_RE.sub(lambda m: store(m.group(0)), text)

	# 2) 이미지
	def image_repl(m: re.Match) -> str:
		alt = _process_backslash_escapes(m.group("alt"))
		src = m.group("src") or ""
		title = m.group("title")
		attrs = f' src="{_escape_html(src)}" alt="{_escape_html(alt)}"'
		if title:
			attrs += f' title="{_escape_html(_process_backslash_escapes(title))}"'
		return store(f"<img{attrs}>")

	text = _IMAGE_RE.sub(image_repl, text)

	# 3) 링크
	def link_repl(m: re.Match) -> str:
		link_text = m.group("text")
		url = m.group("url") or ""
		title = m.group("title")
		inner = render_inline(link_text)
		attrs = f' href="{_escape_html(url)}"'
		if title:
			attrs += f' title="{_escape_html(_process_backslash_escapes(title))}"'
		return store(f"<a{attrs}>{inner}</a>")

	text = _LINK_RE.sub(link_repl, text)

	# 4) 오토링크
	def autolink_repl(m: re.Match) -> str:
		target = m.group(1)
		href = ("mailto:" + target) if "@" in target and "://" not in target else target
		return store(f'<a href="{_escape_html(href)}">{_escape_html(target)}</a>')

	text = _AUTOLINK_RE.sub(autolink_repl, text)

	# 5) 하드 라인브레이크 (이스케이프 전에 처리)
	text = _HARDBREAK_RE.sub(lambda _m: store("<br>") + "\n", text)

	# 6) 남은 HTML 민감 문자 이스케이프
	text = _escape_html(text)

	# 7) 강조: strong → em → strikethrough
	text = _STRONG_RE.sub(lambda m: f"<strong>{m.group(2)}</strong>", text)
	text = _EM_RE.sub(lambda m: f"<em>{m.group(2)}</em>", text)
	text = _STRIKE_RE.sub(lambda m: f"<del>{m.group(1)}</del>", text)

	# 8) 백슬래시 이스케이프 (강조 처리 후에 \* 보존)
	text = _process_backslash_escapes(text)

	# 9) 플레이스홀더 복원
	def restore(s: str) -> str:
		for i, frag in enumerate(placeholders):
			s = s.replace(_placeholder("INL", i), frag)
		return s

	return restore(text)


# --------------------------- 블록 파싱 ----------------------------

_HR_RE = re.compile(r"^ {0,3}(?:-\s*){3,}$|^ {0,3}(?:\*\s*){3,}$|^ {0,3}(?:_\s*){3,}$")
_ATX_RE = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
_FENCE_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})\s*([^\s`~]*)\s*$")
_BLOCKQUOTE_RE = re.compile(r"^ {0,3}>\s?(.*)$")
_UL_RE = re.compile(r"^( *)([-*+])(\s+)(.*)$")
_OL_RE = re.compile(r"^( *)(\d{1,9})([.)])(\s+)(.*)$")
_TABLE_DELIM_RE = re.compile(
	r"^ {0,3}\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)+\|?\s*$"
)
_SETEXT_H1_RE = re.compile(r"^ {0,3}=+\s*$")
_SETEXT_H2_RE = re.compile(r"^ {0,3}-+\s*$")


@dataclass
class _ListItem:
	lines: List[str] = field(default_factory=list)


def _split_table_row(line: str) -> List[str]:
	line = line.strip()
	if line.startswith("|"):
		line = line[1:]
	if line.endswith("|"):
		line = line[:-1]
	cells: List[str] = []
	buf: List[str] = []
	i = 0
	while i < len(line):
		ch = line[i]
		if ch == "\\" and i + 1 < len(line):
			buf.append(line[i + 1])
			i += 2
			continue
		if ch == "|":
			cells.append("".join(buf).strip())
			buf = []
		else:
			buf.append(ch)
		i += 1
	cells.append("".join(buf).strip())
	return cells


def _parse_alignments(delim: str) -> List[str]:
	aligns: List[str] = []
	for cell in _split_table_row(delim):
		cell = cell.strip()
		left = cell.startswith(":")
		right = cell.endswith(":")
		if left and right:
			aligns.append("center")
		elif right:
			aligns.append("right")
		elif left:
			aligns.append("left")
		else:
			aligns.append("")
	return aligns


def _render_table(header: str, delim: str, body: List[str]) -> str:
	aligns = _parse_alignments(delim)
	head_cells = _split_table_row(header)
	out = ["<table>", "<thead>", "<tr>"]
	for i, cell in enumerate(head_cells):
		align = aligns[i] if i < len(aligns) else ""
		attr = f' style="text-align:{align}"' if align else ""
		out.append(f"<th{attr}>{render_inline(cell)}</th>")
	out.append("</tr>")
	out.append("</thead>")
	if body:
		out.append("<tbody>")
		for row in body:
			cells = _split_table_row(row)
			out.append("<tr>")
			for i in range(len(head_cells)):
				cell = cells[i] if i < len(cells) else ""
				align = aligns[i] if i < len(aligns) else ""
				attr = f' style="text-align:{align}"' if align else ""
				out.append(f"<td{attr}>{render_inline(cell)}</td>")
			out.append("</tr>")
		out.append("</tbody>")
	out.append("</table>")
	return "\n".join(out)


def _strip_indent(line: str, n: int) -> str:
	i = 0
	while i < n and i < len(line) and line[i] == " ":
		i += 1
	return line[i:]


def _render_list(items: List[_ListItem], ordered: bool, start: Optional[int]) -> str:
	tag = "ol" if ordered else "ul"
	open_tag = f"<{tag}"
	if ordered and start is not None and start != 1:
		open_tag += f' start="{start}"'
	open_tag += ">"
	parts = [open_tag]

	# tight 판정: 어느 아이템도 본문에 빈 줄을 포함하지 않으면 tight
	tight = True
	for item in items:
		body = "\n".join(item.lines).strip("\n")
		if "\n\n" in body:
			tight = False
			break

	for item in items:
		body_text = "\n".join(item.lines)
		rendered = _convert_blocks(body_text)
		if tight:
			stripped = rendered.strip()
			if stripped.startswith("<p>") and stripped.endswith("</p>") and stripped.count("<p>") == 1:
				stripped = stripped[3:-4]
				parts.append(f"<li>{stripped}</li>")
				continue
			m = re.match(r"^<p>(.*?)</p>\n(.*)$", stripped, re.DOTALL)
			if m and "<p>" not in m.group(2):
				parts.append(f"<li>{m.group(1)}\n{m.group(2)}</li>")
				continue
		parts.append(f"<li>{rendered}</li>" if rendered else "<li></li>")
	parts.append(f"</{tag}>")
	return "\n".join(parts)


def _convert_blocks(source: str) -> str:
	# 라인 엔딩 정규화, 탭을 4칸 공백으로
	lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
	lines = [ln.expandtabs(4) for ln in lines]
	out: List[str] = []
	i = 0
	n = len(lines)

	while i < n:
		line = lines[i]
		stripped = line.strip()

		# 빈 줄
		if stripped == "":
			i += 1
			continue

		# 펜스 코드블록
		m = _FENCE_RE.match(line)
		if m:
			indent = len(m.group(1))
			fence = m.group(2)
			lang = m.group(3) or ""
			i += 1
			buf: List[str] = []
			while i < n:
				cur = lines[i]
				cm = _FENCE_RE.match(cur)
				if cm and cm.group(2)[0] == fence[0] and len(cm.group(2)) >= len(fence) and cm.group(3) == "":
					i += 1
					break
				buf.append(_strip_indent(cur, indent))
				i += 1
			code = "\n".join(buf)
			# JS 포트와 일치: mermaid 는 language- 접두어 제외
			cls_pre = "" if lang == "mermaid" else "language-"
			cls = f' class="{cls_pre}{_escape_html(lang)}"' if lang else ""
			out.append(f"<pre><code{cls}>{_escape_html(code)}</code></pre>")
			continue

		# ATX 헤딩
		m = _ATX_RE.match(line)
		if m:
			level = len(m.group(1))
			content = (m.group(2) or "").strip()
			out.append(f"<h{level}>{render_inline(content)}</h{level}>")
			i += 1
			continue

		# 가로줄
		if _HR_RE.match(line):
			out.append("<hr>")
			i += 1
			continue

		# 인용
		if _BLOCKQUOTE_RE.match(line):
			buf = []
			while i < n and (_BLOCKQUOTE_RE.match(lines[i]) or (lines[i].strip() != "" and not _is_block_start(lines[i]))):
				bm = _BLOCKQUOTE_RE.match(lines[i])
				if bm:
					buf.append(bm.group(1))
				else:
					# lazy continuation
					buf.append(lines[i].lstrip())
				i += 1
				if i < n and lines[i].strip() == "":
					break
			inner = _convert_blocks("\n".join(buf))
			out.append(f"<blockquote>\n{inner}\n</blockquote>")
			continue

		# 표: 헤더 라인 + 구분자 라인
		if "|" in line and i + 1 < n and _TABLE_DELIM_RE.match(lines[i + 1]):
			header = line
			delim = lines[i + 1]
			body: List[str] = []
			i += 2
			while i < n and lines[i].strip() != "" and "|" in lines[i]:
				body.append(lines[i])
				i += 1
			out.append(_render_table(header, delim, body))
			continue

		# 들여쓰기 코드블록 (4칸 이상)
		if line.startswith("    ") and (not out or _is_blank_or_block(lines[i - 1] if i > 0 else "")):
			buf = []
			while i < n and (lines[i].startswith("    ") or lines[i].strip() == ""):
				if lines[i].strip() == "":
					j = i + 1
					while j < n and lines[j].strip() == "":
						j += 1
					if j < n and lines[j].startswith("    "):
						buf.append("")
						i += 1
						continue
					break
				buf.append(lines[i][4:])
				i += 1
			while buf and buf[-1] == "":
				buf.pop()
			out.append(f"<pre><code>{_escape_html(chr(10).join(buf))}</code></pre>")
			continue

		# 리스트
		ul = _UL_RE.match(line)
		ol = _OL_RE.match(line)
		if ul or ol:
			ordered = bool(ol)
			start_num: Optional[int] = int(ol.group(2)) if ol else None
			items, i = _collect_list_items(lines, i, ordered)
			out.append(_render_list(items, ordered, start_num))
			continue

		# Setext 헤딩: 단락 다음 줄이 === 또는 ---
		if i + 1 < n:
			nxt = lines[i + 1]
			if _SETEXT_H1_RE.match(nxt):
				out.append(f"<h1>{render_inline(stripped)}</h1>")
				i += 2
				continue
			if _SETEXT_H2_RE.match(nxt) and not _HR_RE.match(nxt):
				out.append(f"<h2>{render_inline(stripped)}</h2>")
				i += 2
				continue

		# raw HTML 블록 (CommonMark Type 6/7 단순화)
		if stripped.startswith("<"):
			buf = []
			while i < n and lines[i].strip() != "":
				buf.append(lines[i])
				i += 1
			out.append("\n".join(buf))
			continue

		# 단락
		buf = [line.strip()]
		i += 1
		while i < n:
			cur = lines[i]
			if cur.strip() == "":
				break
			if _is_block_start(cur):
				break
			buf.append(cur.strip())
			i += 1
		para = "\n".join(buf)
		out.append(f"<p>{render_inline(para)}</p>")

	return "\n".join(out)


def _is_blank_or_block(line: str) -> bool:
	return line.strip() == "" or _is_block_start(line)


def _is_block_start(line: str) -> bool:
	if _ATX_RE.match(line):
		return True
	if _HR_RE.match(line):
		return True
	if _FENCE_RE.match(line):
		return True
	if _BLOCKQUOTE_RE.match(line):
		return True
	if _UL_RE.match(line) or _OL_RE.match(line):
		return True
	return False


def _collect_list_items(
	lines: List[str], start: int, ordered: bool
) -> Tuple[List[_ListItem], int]:
	items: List[_ListItem] = []
	i = start
	n = len(lines)
	pattern = _OL_RE if ordered else _UL_RE

	while i < n:
		line = lines[i]
		m = pattern.match(line)
		if not m:
			break
		if ordered:
			indent = len(m.group(1))
			marker_len = len(m.group(2)) + 1  # 숫자 + . 또는 )
			spaces = len(m.group(4))
			content = m.group(5)
		else:
			indent = len(m.group(1))
			marker_len = 1
			spaces = len(m.group(3))
			content = m.group(4)

		cont_indent = indent + marker_len + spaces
		item = _ListItem(lines=[content])
		i += 1

		while i < n:
			cur = lines[i]
			if cur.strip() == "":
				j = i + 1
				while j < n and lines[j].strip() == "":
					j += 1
				if j < n and (lines[j].startswith(" " * cont_indent) or pattern.match(lines[j])):
					item.lines.append("")
					i += 1
					continue
				break
			sibling = pattern.match(cur)
			if sibling and len(sibling.group(1)) == indent:
				break
			if not cur.startswith(" " * cont_indent):
				if not _is_block_start(cur):
					item.lines.append(cur.strip())
					i += 1
					continue
				break
			item.lines.append(cur[cont_indent:])
			i += 1

		items.append(item)

	return items, i


# --------------------------- 컨셉 테마 (10종) -------------------------------
# JS 포트(skin/basic/js/md2html.js)의 __MD2HTML_TABS / __MD2HTML_PRESETS 와 1:1 동등

THEMES: List[Tuple[str, str]] = [
	("white",     "White"),
	("dark",      "Dark"),
	("release",   "릴리즈 노트"),
	("meeting",   "회의록"),
	("report",    "업무보고"),
	("proposal",  "제안서"),
	("manual",    "매뉴얼"),
	("notice",    "공지사항"),
	("plan",      "기획안"),
	("quotation", "견적서"),
]

# 한글/별칭 → 표준 ID 매핑 (CLI 친화)
_THEME_ALIASES = {
	"white": "white", "White": "white",
	"dark": "dark", "Dark": "dark",
	"release": "release", "릴리즈": "release", "릴리즈노트": "release", "릴리즈 노트": "release",
	"meeting": "meeting", "회의록": "meeting",
	"report": "report", "업무보고": "report",
	"proposal": "proposal", "제안서": "proposal",
	"manual": "manual", "매뉴얼": "manual",
	"notice": "notice", "공지사항": "notice",
	"plan": "plan", "기획안": "plan",
	"quotation": "quotation", "견적서": "quotation",
}

PRESETS = {
	# 1) White: 깨끗한 화이트, 파란 액센트, 산세리프
	"white": "\n".join([
		'body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "맑은 고딕", sans-serif; color: #1f1f1f; background: #ffffff; line-height: 1.7; max-width: 760px; margin: 0 auto; padding: 48px 24px; }',
		'h1, h2, h3, h4, h5, h6 { color: #111; line-height: 1.3; margin-top: 1.6em; }',
		'h1 { font-size: 2.2em; border-bottom: 2px solid #f0f0f0; padding-bottom: 0.3em; }',
		'h2 { font-size: 1.6em; }',
		'h3 { font-size: 1.25em; }',
		'p { margin: 0.9em 0; }',
		'a { color: #0066cc; text-decoration: none; }',
		'a:hover { text-decoration: underline; }',
		'code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-family: "Consolas", monospace; font-size: 0.92em; color: #d63384; }',
		'pre { background: #f8f8f8; padding: 16px; border-radius: 6px; overflow-x: auto; border: 1px solid #eee; }',
		'pre code { background: transparent; color: inherit; padding: 0; }',
		'blockquote { border-left: 4px solid #e0e0e0; padding: 0.4em 1em; color: #555; margin: 1em 0; }',
		'table { border-collapse: collapse; width: 100%; margin: 1em 0; }',
		'th, td { border: 1px solid #e0e0e0; padding: 8px 12px; }',
		'th { background: #fafafa; }',
		'hr { border: 0; border-top: 1px solid #eee; margin: 2em 0; }',
		'img { max-width: 100%; }',
	]),

	# 2) Dark: VS Code 다크 톤, 청록 링크, 부드러운 회색 본문
	"dark": "\n".join([
		'body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #e4e4e7; background: #18181b; line-height: 1.7; max-width: 820px; margin: 0 auto; padding: 48px 24px; }',
		'h1, h2, h3, h4, h5, h6 { color: #f4f4f5; line-height: 1.3; margin-top: 1.6em; }',
		'h1 { font-size: 2.2em; border-bottom: 1px solid #3f3f46; padding-bottom: 0.3em; }',
		'h2 { font-size: 1.6em; border-bottom: 1px solid #27272a; padding-bottom: 0.25em; }',
		'h3 { font-size: 1.25em; color: #a1a1aa; }',
		'p { margin: 0.9em 0; }',
		'a { color: #38bdf8; text-decoration: none; }',
		'a:hover { color: #7dd3fc; text-decoration: underline; }',
		'code { background: #27272a; padding: 2px 6px; border-radius: 3px; font-family: "Consolas", monospace; color: #fbbf24; }',
		'pre { background: #09090b; padding: 16px; border-radius: 6px; overflow-x: auto; border: 1px solid #27272a; }',
		'pre code { background: transparent; color: #e4e4e7; padding: 0; }',
		'blockquote { border-left: 4px solid #52525b; padding: 0.4em 1em; color: #a1a1aa; background: #27272a; margin: 1em 0; }',
		'table { border-collapse: collapse; width: 100%; margin: 1em 0; }',
		'th, td { border: 1px solid #3f3f46; padding: 8px 12px; }',
		'th { background: #27272a; }',
		'hr { border: 0; border-top: 1px solid #3f3f46; margin: 2em 0; }',
		'strong { color: #ffffff; }',
	]),

	# 3) 릴리즈 노트
	"release": "\n".join([
		'body { font-family: -apple-system, "Apple SD Gothic Neo", "맑은 고딕", sans-serif; color: #1f2937; background: #ffffff; line-height: 1.65; max-width: 880px; margin: 0 auto; padding: 48px 32px; }',
		'h1 { font-size: 1.9em; color: #fff; background: #0f172a; padding: 18px 24px; border-radius: 6px; margin-top: 0; }',
		'h1::before { content: "RELEASE"; display: inline-block; background: #0ea5e9; color: #fff; padding: 4px 10px; border-radius: 4px; font-size: 0.55em; margin-right: 12px; font-weight: 700; letter-spacing: 0.1em; vertical-align: middle; }',
		'h2 { font-size: 1.4em; color: #0f172a; margin-top: 2em; padding: 10px 16px; background: #f1f5f9; border-radius: 6px; border-left: 5px solid #0ea5e9; }',
		'h3 { font-size: 1.15em; color: #334155; margin-top: 1.4em; padding-left: 12px; border-left: 3px solid #cbd5e1; }',
		'p { margin: 0.7em 0; }',
		'a { color: #0284c7; text-decoration: none; border-bottom: 1px dotted #7dd3fc; }',
		'a:hover { border-bottom-style: solid; }',
		'code { background: #f1f5f9; padding: 2px 6px; border-radius: 3px; font-family: ui-monospace, Consolas, monospace; font-size: 0.88em; color: #db2777; border: 1px solid #e2e8f0; }',
		'pre { background: #0f172a; color: #e2e8f0; padding: 14px 18px; border-radius: 6px; overflow-x: auto; font-size: 0.9em; }',
		'pre code { background: transparent; color: inherit; padding: 0; border: 0; }',
		'blockquote { background: #ecfeff; border-left: 4px solid #06b6d4; padding: 12px 16px; margin: 1em 0; color: #155e75; border-radius: 0 4px 4px 0; }',
		'blockquote::before { content: "🔖 노트 "; font-weight: 700; color: #0e7490; }',
		'table { border-collapse: collapse; width: 100%; margin: 1em 0; }',
		'th, td { border: 1px solid #e2e8f0; padding: 8px 12px; }',
		'th { background: #f1f5f9; color: #0f172a; font-weight: 600; }',
		'tr:nth-child(2n) { background: #f8fafc; }',
		'hr { border: 0; border-top: 1px dashed #cbd5e1; margin: 2em 0; }',
		'strong { color: #db2777; }',
		'em { color: #0284c7; font-style: normal; font-weight: 600; }',
		'ul, ol { padding-left: 1.6em; }',
		'li { margin: 0.3em 0; }',
		'ul li::marker { color: #0ea5e9; }',
	]),

	# 4) 회의록 (기본 테마)
	"meeting": "\n".join([
		'body { font-family: -apple-system, "Apple SD Gothic Neo", "맑은 고딕", sans-serif; color: #2d3748; background: #ffffff; line-height: 1.7; max-width: 820px; margin: 0 auto; padding: 48px 32px; }',
		'h1 { font-size: 1.9em; color: #1a365d; padding: 16px 20px; background: #ebf8ff; border-left: 6px solid #2b6cb0; margin-top: 0; border-radius: 4px; }',
		'h2 { font-size: 1.4em; color: #2c5282; margin-top: 2em; padding-bottom: 8px; border-bottom: 2px solid #bee3f8; }',
		'h2::before { content: "■ "; color: #2b6cb0; }',
		'h3 { font-size: 1.15em; color: #2d3748; margin-top: 1.5em; }',
		'h3::before { content: "▸ "; color: #4299e1; }',
		'p { margin: 0.7em 0; }',
		'a { color: #2b6cb0; text-decoration: underline; text-decoration-color: #bee3f8; text-underline-offset: 3px; }',
		'code { background: #edf2f7; padding: 1px 6px; border-radius: 3px; font-family: Consolas, monospace; font-size: 0.9em; color: #c53030; }',
		'pre { background: #f7fafc; padding: 14px 18px; border-left: 4px solid #4299e1; border-radius: 4px; overflow-x: auto; }',
		'pre code { background: transparent; color: #2d3748; }',
		'blockquote { background: #fffaf0; border-left: 4px solid #ed8936; padding: 12px 16px; margin: 1em 0; color: #744210; }',
		'blockquote::before { content: "📌 결정사항 "; font-weight: 700; color: #c05621; }',
		'ul, ol { padding-left: 1.6em; }',
		'li { margin: 0.3em 0; }',
		'ul li::marker { color: #4299e1; }',
		'table { border-collapse: collapse; width: 100%; margin: 1em 0; }',
		'th, td { border: 1px solid #cbd5e0; padding: 8px 12px; text-align: left; }',
		'th { background: #4299e1; color: white; }',
		'tr:nth-child(2n) { background: #f7fafc; }',
		'hr { border: 0; border-top: 2px dashed #cbd5e0; margin: 2em 0; }',
		'strong { color: #c53030; }',
	]),

	# 5) 업무보고
	"report": "\n".join([
		'body { font-family: -apple-system, "Apple SD Gothic Neo", "맑은 고딕", sans-serif; color: #1f2937; background: #ffffff; line-height: 1.65; max-width: 880px; margin: 0 auto; padding: 48px 32px; font-size: 15px; }',
		'h1 { font-size: 2em; color: #111827; padding-bottom: 12px; border-bottom: 3px double #374151; margin-top: 0; }',
		'h2 { font-size: 1.45em; color: #111827; padding: 10px 16px; background: linear-gradient(to right, #f3f4f6, transparent); border-left: 5px solid #374151; margin-top: 2em; }',
		'h3 { font-size: 1.15em; color: #374151; margin-top: 1.5em; }',
		'h3::before { content: "▣ "; color: #6b7280; }',
		'p { margin: 0.7em 0; }',
		'a { color: #1d4ed8; text-decoration: none; border-bottom: 1px solid #93c5fd; }',
		'code { background: #f3f4f6; padding: 1px 6px; border-radius: 3px; font-family: Consolas, monospace; font-size: 0.9em; color: #374151; }',
		'pre { background: #f9fafb; padding: 14px 18px; border: 1px solid #e5e7eb; border-radius: 4px; overflow-x: auto; }',
		'pre code { background: transparent; }',
		'blockquote { background: #f9fafb; border-left: 4px solid #6b7280; padding: 10px 16px; margin: 1em 0; color: #4b5563; font-size: 0.95em; }',
		'table { border-collapse: collapse; width: 100%; margin: 1.2em 0; font-size: 0.93em; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }',
		'th, td { border: 1px solid #d1d5db; padding: 8px 12px; }',
		'th { background: #1f2937; color: #f9fafb; font-weight: 600; text-align: center; }',
		'tr:nth-child(2n) { background: #f9fafb; }',
		'td:first-child { font-weight: 600; }',
		'hr { border: 0; border-top: 1px solid #d1d5db; margin: 2em 0; }',
		'strong { color: #1f2937; background: #fef3c7; padding: 0 2px; }',
		'ul, ol { padding-left: 1.6em; }',
	]),

	# 6) 제안서
	"proposal": "\n".join([
		'body { font-family: -apple-system, "Apple SD Gothic Neo", "맑은 고딕", sans-serif; color: #1e293b; background: #ffffff; line-height: 1.7; max-width: 900px; margin: 0 auto; padding: 56px 40px; }',
		'h1 { font-size: 2.6em; color: #fff; background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); padding: 32px 28px; margin: -56px -40px 32px; letter-spacing: -0.01em; }',
		'h2 { font-size: 1.7em; color: #1e3a8a; margin-top: 2em; padding-bottom: 8px; position: relative; }',
		'h2::after { content: ""; display: block; width: 50px; height: 4px; background: #3b82f6; margin-top: 8px; border-radius: 2px; }',
		'h3 { font-size: 1.25em; color: #1e40af; margin-top: 1.5em; }',
		'h3::before { content: "◆ "; color: #3b82f6; }',
		'p { margin: 1em 0; }',
		'a { color: #2563eb; font-weight: 600; text-decoration: none; }',
		'a:hover { text-decoration: underline; }',
		'code { background: #eff6ff; padding: 2px 6px; border-radius: 3px; font-family: Consolas, monospace; font-size: 0.9em; color: #1e40af; }',
		'pre { background: #f8fafc; padding: 16px 20px; border-radius: 8px; border: 1px solid #e2e8f0; overflow-x: auto; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }',
		'pre code { background: transparent; }',
		'blockquote { background: #eff6ff; border-left: 5px solid #3b82f6; padding: 16px 20px; margin: 1.2em 0; border-radius: 0 8px 8px 0; color: #1e40af; font-style: italic; }',
		'table { border-collapse: collapse; width: 100%; margin: 1.2em 0; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }',
		'th, td { padding: 12px 16px; border-bottom: 1px solid #e2e8f0; }',
		'th { background: #1e3a8a; color: #fff; text-align: left; }',
		'tr:nth-child(2n) { background: #f8fafc; }',
		'hr { border: 0; height: 3px; background: linear-gradient(90deg, #1e3a8a, #3b82f6, transparent); margin: 2.5em 0; border-radius: 2px; }',
		'strong { color: #1e3a8a; }',
		'em { color: #3b82f6; font-style: normal; font-weight: 600; }',
		'ul, ol { padding-left: 1.6em; }',
		'li { margin: 0.4em 0; }',
	]),

	# 7) 매뉴얼
	"manual": "\n".join([
		'body { font-family: -apple-system, "Apple SD Gothic Neo", "맑은 고딕", sans-serif; color: #24292f; background: #ffffff; line-height: 1.6; max-width: 920px; margin: 0 auto; padding: 40px 32px; }',
		'h1 { font-size: 2.1em; color: #1f2328; padding-bottom: 12px; border-bottom: 1px solid #d0d7de; margin-top: 0; }',
		'h2 { font-size: 1.5em; color: #1f2328; padding: 8px 0 8px 14px; border-left: 4px solid #fd8c73; margin-top: 2em; background: linear-gradient(to right, #fff8f0, transparent 60%); }',
		'h3 { font-size: 1.2em; color: #57606a; margin-top: 1.4em; padding-left: 8px; border-left: 2px solid #d0d7de; }',
		'p { margin: 0.7em 0; }',
		'a { color: #0969da; text-decoration: none; }',
		'a:hover { text-decoration: underline; }',
		'code { background: #f6f8fa; padding: 2px 6px; border-radius: 4px; font-family: ui-monospace, "SFMono-Regular", Consolas, monospace; font-size: 0.88em; color: #cf222e; border: 1px solid #d0d7de; }',
		'pre { background: #0d1117; color: #c9d1d9; padding: 14px 18px; border-radius: 6px; overflow-x: auto; line-height: 1.5; font-size: 0.9em; position: relative; }',
		'pre::before { content: "CODE"; position: absolute; top: 8px; right: 12px; font-size: 10px; color: #8b949e; letter-spacing: 0.1em; font-family: monospace; }',
		'pre code { background: transparent; color: inherit; padding: 0; border: 0; }',
		'blockquote { background: #ddf4ff; border-left: 4px solid #54aeff; padding: 12px 16px; margin: 1em 0; color: #0550ae; border-radius: 0 4px 4px 0; }',
		'blockquote::before { content: "💡 참고 "; font-weight: 700; color: #0969da; }',
		'table { border-collapse: collapse; width: 100%; margin: 1em 0; }',
		'th, td { border: 1px solid #d0d7de; padding: 8px 12px; }',
		'th { background: #f6f8fa; font-weight: 600; }',
		'tr:nth-child(2n) { background: #f6f8fa; }',
		'hr { border: 0; border-top: 1px solid #d0d7de; margin: 2em 0; }',
		'strong { color: #cf222e; }',
		'ul, ol { padding-left: 1.6em; }',
	]),

	# 8) 공지사항
	"notice": "\n".join([
		'body { font-family: -apple-system, "Apple SD Gothic Neo", "맑은 고딕", sans-serif; color: #1f2937; background: #fffbf5; line-height: 1.75; max-width: 760px; margin: 0 auto; padding: 48px 32px; }',
		'h1 { font-size: 2em; color: #fff; background: #dc2626; padding: 18px 24px; border-radius: 8px; margin-top: 0; box-shadow: 0 4px 12px rgba(220, 38, 38, 0.25); }',
		'h1::before { content: "📢 "; }',
		'h2 { font-size: 1.4em; color: #991b1b; margin-top: 2em; padding: 8px 14px; background: #fee2e2; border-radius: 4px; border-left: 5px solid #dc2626; }',
		'h3 { font-size: 1.15em; color: #b45309; margin-top: 1.4em; }',
		'h3::before { content: "● "; color: #f59e0b; }',
		'p { margin: 0.8em 0; }',
		'a { color: #b45309; font-weight: 600; text-decoration: underline; text-decoration-style: wavy; text-underline-offset: 4px; }',
		'code { background: #fef3c7; padding: 2px 6px; border-radius: 3px; font-family: Consolas, monospace; font-size: 0.92em; color: #92400e; }',
		'pre { background: #fffbeb; padding: 14px 18px; border: 2px dashed #fbbf24; border-radius: 6px; overflow-x: auto; }',
		'pre code { background: transparent; }',
		'blockquote { background: #fef2f2; border: 2px solid #fecaca; border-left: 6px solid #dc2626; padding: 14px 18px; margin: 1.2em 0; border-radius: 6px; color: #7f1d1d; font-weight: 500; }',
		'blockquote::before { content: "⚠ 중요 "; font-weight: 700; color: #dc2626; }',
		'table { border-collapse: collapse; width: 100%; margin: 1em 0; background: #fff; border-radius: 6px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }',
		'th, td { padding: 10px 14px; border-bottom: 1px solid #fde68a; }',
		'th { background: #fbbf24; color: #78350f; font-weight: 700; }',
		'hr { border: 0; border-top: 2px dotted #fbbf24; margin: 2em 0; }',
		'strong { color: #dc2626; background: #fef3c7; padding: 0 4px; border-radius: 2px; }',
		'ul, ol { padding-left: 1.6em; }',
	]),

	# 9) 기획안
	"plan": "\n".join([
		'body { font-family: -apple-system, "Apple SD Gothic Neo", "맑은 고딕", sans-serif; color: #1f2937; background: #ffffff; line-height: 1.7; max-width: 900px; margin: 0 auto; padding: 48px 32px; counter-reset: section; }',
		'h1 { font-size: 2.2em; color: #5b21b6; padding-bottom: 16px; border-bottom: 4px solid #7c3aed; margin-top: 0; letter-spacing: -0.01em; }',
		'h1::before { content: "PLAN"; display: block; font-size: 0.4em; color: #a78bfa; letter-spacing: 0.3em; font-weight: 600; margin-bottom: 4px; }',
		'h2 { font-size: 1.5em; color: #5b21b6; margin-top: 2em; padding: 10px 0 10px 18px; border-left: 6px solid #8b5cf6; background: #f5f3ff; counter-increment: section; }',
		'h2::before { content: counter(section) ". "; color: #7c3aed; font-weight: 700; }',
		'h3 { font-size: 1.2em; color: #6d28d9; margin-top: 1.5em; }',
		'h3::before { content: "▶ "; color: #8b5cf6; }',
		'p { margin: 0.7em 0; }',
		'a { color: #7c3aed; text-decoration: none; border-bottom: 2px solid #ddd6fe; }',
		'a:hover { border-bottom-color: #7c3aed; }',
		'code { background: #ede9fe; padding: 2px 6px; border-radius: 3px; font-family: Consolas, monospace; font-size: 0.9em; color: #5b21b6; }',
		'pre { background: #faf5ff; padding: 14px 18px; border-left: 4px solid #8b5cf6; border-radius: 4px; overflow-x: auto; }',
		'pre code { background: transparent; }',
		'blockquote { background: #ecfdf5; border-left: 4px solid #10b981; padding: 12px 18px; margin: 1em 0; border-radius: 0 4px 4px 0; color: #064e3b; }',
		'blockquote::before { content: "🎯 목표 "; font-weight: 700; color: #047857; }',
		'table { border-collapse: collapse; width: 100%; margin: 1.2em 0; }',
		'th, td { border: 1px solid #e5e7eb; padding: 10px 14px; }',
		'th { background: linear-gradient(135deg, #7c3aed 0%, #8b5cf6 100%); color: #fff; }',
		'tr:nth-child(2n) { background: #faf5ff; }',
		'hr { border: 0; height: 2px; background: linear-gradient(90deg, #7c3aed, #10b981); margin: 2em 0; }',
		'strong { color: #5b21b6; }',
		'em { color: #047857; font-weight: 600; font-style: normal; }',
		'ul, ol { padding-left: 1.6em; }',
		'li::marker { color: #7c3aed; }',
	]),

	# 10) 견적서
	"quotation": "\n".join([
		'body { font-family: -apple-system, "Apple SD Gothic Neo", "맑은 고딕", sans-serif; color: #1f2937; background: #ffffff; line-height: 1.6; max-width: 860px; margin: 0 auto; padding: 48px 36px; }',
		'h1 { font-size: 2.4em; color: #064e3b; text-align: center; margin: 0 0 32px; padding-bottom: 16px; border-bottom: 3px double #047857; letter-spacing: 0.05em; font-weight: 800; }',
		'h2 { font-size: 1.35em; color: #065f46; margin-top: 1.8em; padding: 8px 0 8px 14px; border-left: 5px solid #10b981; background: #f0fdf4; }',
		'h3 { font-size: 1.1em; color: #1f2937; margin-top: 1.4em; }',
		'h3::before { content: "■ "; color: #10b981; }',
		'p { margin: 0.6em 0; }',
		'a { color: #047857; text-decoration: underline; }',
		'code { background: #f3f4f6; padding: 2px 5px; border-radius: 3px; font-family: Consolas, monospace; font-size: 0.9em; color: #374151; }',
		'pre { background: #f9fafb; padding: 14px 18px; border: 1px solid #e5e7eb; border-radius: 4px; overflow-x: auto; }',
		'pre code { background: transparent; }',
		'blockquote { background: #f9fafb; border-left: 4px solid #6b7280; padding: 10px 16px; margin: 1em 0; color: #4b5563; font-size: 0.95em; }',
		'table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.94em; }',
		'th, td { border: 1px solid #d1d5db; padding: 10px 12px; }',
		'th { background: #047857; color: #fff; text-align: center; font-weight: 600; }',
		'tr:nth-child(2n) { background: #f9fafb; }',
		'td:nth-child(n+2) { text-align: right; }',
		'td:nth-child(1) { text-align: left; font-weight: 600; }',
		'tr:last-child { background: #d1fae5; font-weight: 700; }',
		'tr:last-child td { border-top: 2px solid #047857; color: #064e3b; }',
		'hr { border: 0; border-top: 1px solid #d1d5db; margin: 2em 0; }',
		'strong { color: #047857; }',
		'em { color: #1f2937; font-weight: 600; font-style: normal; background: #fef3c7; padding: 0 4px; }',
		'ul, ol { padding-left: 1.6em; }',
	]),
}

DEFAULT_THEME = "meeting"


def resolve_theme(name: str) -> str:
	"""한글/별칭 입력을 표준 테마 ID로 변환한다. 미지원이면 ValueError."""
	if not name:
		return DEFAULT_THEME
	key = name.strip()
	if key in _THEME_ALIASES:
		return _THEME_ALIASES[key]
	# 공백 무시 매칭 (예: "릴리즈 노트" / "릴리즈노트")
	compact = key.replace(" ", "")
	for k, v in _THEME_ALIASES.items():
		if k.replace(" ", "") == compact:
			return v
	raise ValueError(f"지원하지 않는 테마: {name}")


# --------------------------- 공개 API -------------------------------


def convert(markdown_text: str) -> str:
	"""마크다운 텍스트를 HTML 프래그먼트로 변환한다."""
	return _convert_blocks(markdown_text)


def convert_document(
	markdown_text: str,
	title: str = "",
	lang: str = "ko",
	theme: str = DEFAULT_THEME,
) -> str:
	"""테마 CSS가 인라인으로 포함된 완전한 HTML 문서를 반환한다."""
	theme_id = resolve_theme(theme)
	css = PRESETS[theme_id]
	body = convert(markdown_text)
	return (
		f'<!DOCTYPE html>\n<html lang="{html.escape(lang)}">\n<head>\n'
		f'<meta charset="utf-8">\n'
		f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
		f"<title>{html.escape(title)}</title>\n"
		f'<style>\n{css}\n</style>\n'
		f'</head>\n<body>\n<div class="container">\n{body}\n</div>\n</body>\n</html>\n'
	)


# --------------------------- CLI --------------------------------------


def _list_themes_text() -> str:
	lines = ["지원 테마 (id : 이름):"]
	for tid, tname in THEMES:
		mark = " (기본)" if tid == DEFAULT_THEME else ""
		lines.append(f"  - {tid:10s} : {tname}{mark}")
	return "\n".join(lines)


def _cli(argv: Optional[List[str]] = None) -> int:
	parser = argparse.ArgumentParser(
		description=(
			"Markdown 파일을 단일 HTML 문서로 변환한다. "
			"출력 경로를 생략하면 입력 파일과 같은 디렉토리에 같은 이름의 .html 파일을 생성한다."
		),
		formatter_class=argparse.RawDescriptionHelpFormatter,
		epilog=_list_themes_text(),
	)
	parser.add_argument(
		"input", nargs="?", help="Markdown 파일 경로 (생략 시 stdin)"
	)
	parser.add_argument(
		"-t", "--theme",
		default=DEFAULT_THEME,
		help=f"테마 ID 또는 한글 이름 (기본값: {DEFAULT_THEME} / 회의록)",
	)
	parser.add_argument(
		"-o", "--output",
		help="HTML 출력 경로 (생략 시 입력 파일과 같은 디렉토리에 .html 생성, stdin 입력 시 stdout)",
	)
	parser.add_argument(
		"--title", default="", help="문서 title (생략 시 입력 파일명 사용)"
	)
	parser.add_argument(
		"--lang", default="ko", help="문서 lang 속성 (기본값: ko)"
	)
	parser.add_argument(
		"--stdout", action="store_true",
		help="파일 입력이어도 결과를 stdout 으로 출력한다 (-o 보다 우선)",
	)
	parser.add_argument(
		"--list-themes", action="store_true",
		help="지원 테마 목록을 출력하고 종료",
	)
	args = parser.parse_args(argv)

	if args.list_themes:
		sys.stdout.write(_list_themes_text() + "\n")
		return 0

	# 테마 검증
	try:
		theme_id = resolve_theme(args.theme)
	except ValueError as e:
		sys.stderr.write(f"오류: {e}\n\n{_list_themes_text()}\n")
		return 2

	# 입력 로드
	if args.input:
		try:
			with open(args.input, "r", encoding="utf-8") as f:
				md = f.read()
		except OSError as e:
			sys.stderr.write(f"오류: 입력 파일을 열 수 없습니다 - {e}\n")
			return 1
		if not args.title:
			args.title = os.path.splitext(os.path.basename(args.input))[0]
	else:
		md = sys.stdin.read()

	rendered = convert_document(md, title=args.title, lang=args.lang, theme=theme_id)

	# 출력 경로 결정
	# 우선순위: --stdout > -o > (input 있으면 자동 경로) > stdout
	if args.stdout or (not args.input and not args.output):
		sys.stdout.write(rendered)
		if not rendered.endswith("\n"):
			sys.stdout.write("\n")
		return 0

	if args.output:
		out_path = args.output
	else:
		# 입력 파일과 같은 디렉토리에 같은 이름의 .html
		base, _ext = os.path.splitext(args.input)
		out_path = base + ".html"

	try:
		with open(out_path, "w", encoding="utf-8") as f:
			f.write(rendered)
			if not rendered.endswith("\n"):
				f.write("\n")
	except OSError as e:
		sys.stderr.write(f"오류: 출력 파일을 쓸 수 없습니다 - {e}\n")
		return 1

	sys.stderr.write(f"생성 완료: {out_path}  (테마: {theme_id})\n")
	return 0


if __name__ == "__main__":
	raise SystemExit(_cli())
