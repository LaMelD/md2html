---
name: md2html
description: Markdown 파일을 md2html.py 로 HTML 로 변환한다. "md를 html로 바꿔줘", "이 디렉토리 일괄 변환", "테마를 release로 다시 변환", "README.md도 강제로 변환", "변환 로그 보여줘" 등 수동 변환/재변환/배치 작업이 필요할 때 사용한다.
---

# md2html 수동 변환 스킬

본 플러그인의 PostToolUse 훅(`md2html-auto.sh`)이 모든 `Write`/`Edit`/`MultiEdit` 호출 결과를 자동 변환한다. 이 스킬은 훅이 처리하지 못하는 경우(일괄 변환, 테마 재변환, 자동 제외된 파일 강제 변환)를 보완한다.

## 언제 사용하나

- **일괄 변환**: "docs/ 폴더 전체 변환해줘"
- **테마 변경**: "이 파일을 release 테마로 다시 변환"
- **제외 파일 강제 변환**: "README.md 도 변환해줘" (훅이 자동 제외하는 파일)
- **외부 .md 변환**: 다른 경로의 파일을 변환
- **로그 확인**: "최근 변환 로그 보여줘"
- **테마 목록**: "지원 테마 알려줘"

자동 훅이 처리하는 일상적인 .md 저장 → .html 생성은 이 스킬을 호출할 필요가 없다.

## md2html.py 위치

플러그인 번들 스크립트를 우선 사용한다.

```bash
SCRIPT="${CLAUDE_PLUGIN_ROOT}/scripts/md2html.py"
[[ -f "$SCRIPT" ]] || SCRIPT="$(ls -1 \
  "${MD2HTML_SCRIPT:-}" \
  "$HOME/.local/share/md2html/md2html.py" \
  "$HOME/md2html/md2html.py" \
  /opt/md2html/md2html.py 2>/dev/null | head -1)"
```

`${CLAUDE_PLUGIN_ROOT}` 는 플러그인 훅/스킬 실행 시 자동 주입되는 환경변수다.

## 지원 테마

| ID | 한글 | 용도 |
|---|---|---|
| `meeting` | 회의록 | 회의록 (md2html.py 자체 기본값) |
| `white` | 화이트 | 일반 문서, 깔끔함 |
| `dark` | 다크 | 다크 톤 |
| `release` | 릴리즈노트 | 릴리즈 노트 |
| `report` | 업무보고 | 보고서, 표 강조 |
| `proposal` | 제안서 | 표지 + 진한 푸른 톤 |
| `manual` | 매뉴얼 | 기술 문서 (**훅 기본값**) |
| `notice` | 공지사항 | 강한 빨강 헤더 |
| `plan` | 기획안 | 보라 톤, 자동 번호 |
| `quotation` | 견적서 | 비즈니스 그린, 우측 정렬 |

테마 확인: `python3 "$SCRIPT" --list-themes`

## 작업 패턴

### 1) 단일 파일 재변환 (다른 테마로)

```bash
python3 "$SCRIPT" /abs/path/to/file.md -t release
```

### 2) 디렉토리 일괄 변환

기본적으로 시스템 파일과 제외 디렉토리를 건너뛴다 (훅과 동일 규칙).

```bash
TARGET="/abs/path/to/dir"
THEME="${1:-manual}"

find "$TARGET" -type f \( -iname '*.md' -o -iname '*.markdown' \) \
  ! -path '*/.git/*' \
  ! -path '*/.claude/*' \
  ! -path '*/node_modules/*' \
  ! -path '*/memory/*' \
  ! -path '*/.venv/*' \
  ! -path '*/venv/*' \
  ! -path '*/dist/*' \
  ! -path '*/build/*' \
  ! -name 'CLAUDE.md' \
  ! -name 'AGENTS.md' \
  ! -name 'GEMINI.md' \
  ! -name 'README.md' \
  ! -name 'MEMORY.md' \
  ! -name 'CHANGELOG.md' \
  ! -name 'LICENSE.md' \
  ! -name 'CONTRIBUTING.md' \
  ! -name 'CODE_OF_CONDUCT.md' \
  -print0 |
while IFS= read -r -d '' f; do
  out="${f%.*}.html"
  python3 "$SCRIPT" "$f" -t "$THEME" -o "$out" && echo "✓ $f"
done
```

### 3) 강제 변환 (제외 규칙 무시)

`README.md` 등을 명시적으로 변환:
```bash
python3 "$SCRIPT" /abs/path/to/README.md -t white -o /abs/path/to/README.html
```

### 4) 변환 로그 확인

```bash
tail -50 ~/.claude/logs/md2html.log
```

특정 파일 변환 이력:
```bash
grep -F '<파일명>' ~/.claude/logs/md2html.log | tail -20
```

### 5) 자동 변환 임시 비활성화

긴 세션 동안 끄려면 사용자가 셸에서 `export MD2HTML_SKIP=1` 후 Claude Code 재실행을 안내한다. 한 번의 호출에 대해서만 우회할 수는 없다 (훅은 항상 실행됨).

## 안내할 때 유의 사항

- **이미 변환된 .html 파일은 사용자가 직접 편집하지 않도록 안내한다.** .md 가 단일 진실 원본이고, 훅이 자동으로 .html 을 덮어쓴다.
- 사용자가 "테마 바꿔서 다시" 요청하면 변환만 수행하고 원본 .md 는 건드리지 않는다.
- 한글 테마 이름(`릴리즈노트`, `회의록` 등)도 그대로 `-t` 인자로 전달 가능하다.
- 변환 후 결과 파일 경로를 사용자에게 출력해 브라우저에서 바로 열 수 있게 한다.

## 외부 의존성

`md2html.py` 는 표준 라이브러리만 사용한다. `pip install` 불필요. Python 3.7+ 만 있으면 동작한다.
