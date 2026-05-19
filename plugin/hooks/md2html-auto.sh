#!/usr/bin/env bash
# md2html-auto.sh — PostToolUse hook for md2html plugin
#
# 동작:
#   - stdin 으로 PostToolUse JSON 을 받음
#   - Write/Edit/MultiEdit 결과로 생성/수정된 .md 파일을 자동으로 .html 로 변환
#   - 제외 패턴에 걸리면 스킵, 변환 실패해도 항상 exit 0 (Claude 작업 비차단)
#
# 환경 변수:
#   MD2HTML_SKIP=1          → 전체 비활성화 (긴급 우회)
#   MD2HTML_THEME=<id>      → 기본 테마 오버라이드 (기본: manual)
#   MD2HTML_SCRIPT=<path>   → md2html.py 경로 오버라이드
#   MD2HTML_LOG=<path>      → 로그 경로 오버라이드
#   MD2HTML_DEBUG=1         → 상세 디버그 로그

set -u

# ────────────────────────────────────────────────────────────────────────────
# 1. 항상 성공으로 종료 (Claude 작업 비차단)
# ────────────────────────────────────────────────────────────────────────────
trap 'exit 0' EXIT

# ────────────────────────────────────────────────────────────────────────────
# 2. 빠른 비활성화
# ────────────────────────────────────────────────────────────────────────────
if [[ "${MD2HTML_SKIP:-0}" == "1" ]]; then
  exit 0
fi

# ────────────────────────────────────────────────────────────────────────────
# 3. 로그 설정
# ────────────────────────────────────────────────────────────────────────────
LOG_FILE="${MD2HTML_LOG:-$HOME/.claude/logs/md2html.log}"
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || LOG_FILE=/dev/null

log() {
  local level="$1"; shift
  printf '[%s] [%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$level" "$*" >> "$LOG_FILE" 2>/dev/null || true
}

debug() {
  [[ "${MD2HTML_DEBUG:-0}" == "1" ]] && log DEBUG "$@"
}

# ────────────────────────────────────────────────────────────────────────────
# 4. stdin JSON 파싱
# ────────────────────────────────────────────────────────────────────────────
PAYLOAD="$(cat 2>/dev/null || true)"
if [[ -z "$PAYLOAD" ]]; then
  debug "empty stdin, skip"
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  log WARN "jq not found, plugin md2html hook disabled"
  exit 0
fi

TOOL_NAME="$(jq -r '.tool_name // empty' <<<"$PAYLOAD" 2>/dev/null)"
FILE_PATH="$(jq -r '.tool_input.file_path // empty' <<<"$PAYLOAD" 2>/dev/null)"

debug "tool=$TOOL_NAME file=$FILE_PATH"

# ────────────────────────────────────────────────────────────────────────────
# 5. 도구 필터
# ────────────────────────────────────────────────────────────────────────────
case "$TOOL_NAME" in
  Write|Edit|MultiEdit) ;;
  *) debug "tool $TOOL_NAME not handled, skip"; exit 0 ;;
esac

# ────────────────────────────────────────────────────────────────────────────
# 6. 파일 경로 검증
# ────────────────────────────────────────────────────────────────────────────
if [[ -z "$FILE_PATH" ]]; then
  debug "no file_path, skip"
  exit 0
fi

# 확장자 .md / .markdown 만
shopt -s nocasematch
if [[ ! "$FILE_PATH" =~ \.(md|markdown)$ ]]; then
  debug "not markdown, skip"
  exit 0
fi
shopt -u nocasematch

if [[ ! -f "$FILE_PATH" ]]; then
  debug "file missing: $FILE_PATH"
  exit 0
fi

if [[ ! -s "$FILE_PATH" ]]; then
  debug "empty file: $FILE_PATH"
  exit 0
fi

# ────────────────────────────────────────────────────────────────────────────
# 7. 제외 패턴
# ────────────────────────────────────────────────────────────────────────────
BASENAME="$(basename "$FILE_PATH")"

# 7-1. 시스템/메타 파일 (basename 매칭)
case "$BASENAME" in
  CLAUDE.md|AGENTS.md|GEMINI.md|README.md|MEMORY.md|CHANGELOG.md|LICENSE.md|CONTRIBUTING.md|CODE_OF_CONDUCT.md|SKILL.md)
    debug "system file: $BASENAME"
    exit 0
    ;;
esac

# 7-2. 경로 패턴 매칭
case "$FILE_PATH" in
  */.claude/*|*/.claude-plugin/*|*/.git/*|*/node_modules/*|*/memory/*|*/.venv/*|*/venv/*|*/dist/*|*/build/*|*/.next/*|*/.cache/*)
    debug "excluded path: $FILE_PATH"
    exit 0
    ;;
esac

# ────────────────────────────────────────────────────────────────────────────
# 8. md2html.py 찾기
#    번들된 스크립트(${CLAUDE_PLUGIN_ROOT}/scripts/md2html.py) 우선,
#    실패 시 외부 후보 경로 순차 탐색
# ────────────────────────────────────────────────────────────────────────────
find_script() {
  if [[ -n "${MD2HTML_SCRIPT:-}" && -f "$MD2HTML_SCRIPT" ]]; then
    echo "$MD2HTML_SCRIPT"; return 0
  fi
  local candidates=(
    "${CLAUDE_PLUGIN_ROOT:-}/scripts/md2html.py"
    "$HOME/.local/share/md2html/md2html.py"
    "$HOME/md2html/md2html.py"
    "/home/sjlee4628/md2html/md2html.py"
    "/opt/md2html/md2html.py"
  )
  local c
  for c in "${candidates[@]}"; do
    [[ -z "$c" ]] && continue
    [[ -f "$c" ]] && { echo "$c"; return 0; }
  done
  return 1
}

SCRIPT="$(find_script)"
if [[ -z "$SCRIPT" ]]; then
  log WARN "md2html.py not found (CLAUDE_PLUGIN_ROOT=${CLAUDE_PLUGIN_ROOT:-unset}). file=$FILE_PATH"
  exit 0
fi

# ────────────────────────────────────────────────────────────────────────────
# 9. 변환 실행
# ────────────────────────────────────────────────────────────────────────────
THEME="${MD2HTML_THEME:-manual}"
PYTHON="${MD2HTML_PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  log WARN "python3 not found, skip. file=$FILE_PATH"
  exit 0
fi

OUTPUT="${FILE_PATH%.*}.html"

if STDERR=$("$PYTHON" "$SCRIPT" "$FILE_PATH" -t "$THEME" -o "$OUTPUT" 2>&1 >/dev/null); then
  log INFO "converted [$TOOL_NAME] theme=$THEME file=$FILE_PATH → $OUTPUT"
  debug "stderr: $STDERR"
else
  RC=$?
  log ERROR "convert failed rc=$RC theme=$THEME file=$FILE_PATH stderr=$STDERR"
fi

exit 0
