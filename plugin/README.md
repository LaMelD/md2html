# md2html — Claude Code 자동 변환 플러그인

Claude Code 가 `Write` / `Edit` / `MultiEdit` 도구로 `.md` 파일을 만들거나 수정할 때마다, PostToolUse 훅이 자동으로 `md2html.py` 를 실행해 같은 디렉토리에 `.html` 을 생성한다.

## 특징

- **자동 변환** PostToolUse 훅이 백그라운드에서 동작. 명시적 명령 불필요
- **자기완결** md2html.py 가 플러그인에 번들. 외부 pip 패키지 0개
- **테마 10종** manual(기본) / meeting / white / dark / release / report / proposal / notice / plan / quotation. 한글 별칭 지원
- **안전 제외** CLAUDE.md, README.md, .git, node_modules, dist, build 등 자동 스킵
- **비차단** 변환 실패해도 Claude 작업을 막지 않음 (훅은 항상 exit 0)
- **수동 보완** `md2html` 스킬로 일괄 변환, 테마 재변환, 강제 변환 가능

## 설치

### 로컬 디렉토리에서 설치

```bash
# Claude Code 안에서
/plugin install /home/sjlee4628/md2html/plugin
/reload-plugins
```

### marketplace 로 게시한 경우

```bash
/plugin install md2html
```

설치 후 새 세션을 시작하면 자동 동작한다.

## 동작 흐름

```
Claude 가 .md 작성/수정
   ↓
PostToolUse 훅 발화 (Write|Edit|MultiEdit)
   ↓
${CLAUDE_PLUGIN_ROOT}/hooks/md2html-auto.sh 호출
   ↓
stdin JSON → tool_name / file_path 파싱
   ↓
.md 확장자 + 제외 패턴 + 파일 존재 + 비어있지 않음
   ↓
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/md2html.py <file> -t manual -o <file>.html
   ↓
같은 디렉토리에 .html 생성
```

## 제외 규칙

| 분류 | 패턴 |
|------|------|
| 시스템 파일 (basename) | `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `README.md`, `MEMORY.md`, `CHANGELOG.md`, `LICENSE.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SKILL.md` |
| 경로 패턴 | `*/.claude/*`, `*/.claude-plugin/*`, `*/.git/*`, `*/node_modules/*`, `*/memory/*`, `*/.venv/*`, `*/venv/*`, `*/dist/*`, `*/build/*`, `*/.next/*`, `*/.cache/*` |
| 그 외 | 빈 파일 (0 byte), `.md` / `.markdown` 외 확장자 |

자동 제외된 파일도 `md2html` 스킬로 명시 요청하면 강제 변환된다.

## 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `MD2HTML_SKIP` | (unset) | `1` 이면 훅 전체 비활성화 |
| `MD2HTML_THEME` | `manual` | 기본 테마 ID 또는 한글 별칭 |
| `MD2HTML_SCRIPT` | (자동) | md2html.py 절대 경로 오버라이드 |
| `MD2HTML_PYTHON` | `python3` | Python 인터프리터 |
| `MD2HTML_LOG` | `~/.claude/logs/md2html.log` | 로그 파일 경로 |
| `MD2HTML_DEBUG` | (unset) | `1` 이면 디버그 로그까지 기록 |

세션 전체 테마 변경:
```bash
export MD2HTML_THEME=release
claude
```

## md2html.py 탐색 우선순위

훅은 다음 순서로 변환기를 찾는다.
1. `$MD2HTML_SCRIPT`
2. `${CLAUDE_PLUGIN_ROOT}/scripts/md2html.py` (번들)
3. `~/.local/share/md2html/md2html.py`
4. `~/md2html/md2html.py`
5. `/home/sjlee4628/md2html/md2html.py`
6. `/opt/md2html/md2html.py`

번들이 항상 첫 후보이므로 기본 설치만으로 동작한다. 외부 위치에서 최신 버전을 쓰고 싶을 때만 `MD2HTML_SCRIPT` 를 지정한다.

## 수동 작업 (Skill)

Claude Code 세션 안에서 자연어로 요청한다.

- "이 디렉토리 모든 .md 를 release 테마로 일괄 변환해줘"
- "README.md 도 white 테마로 변환해줘" (제외 우회)
- "최근 변환 로그 보여줘"
- "지원 테마 목록 알려줘"
- "방금 만든 파일을 dark 테마로 다시 변환"

스킬은 훅과 같은 제외 규칙을 기본 적용하지만, 명시 요청한 파일은 강제 변환한다.

## 의존성

- Python 3.7+
- `jq` (훅 JSON 파싱)
- bash 4+

번들된 `md2html.py` 는 표준 라이브러리만 사용한다.

## 트러블슈팅

**.md 를 저장해도 .html 이 안 생긴다**
1. 로그 확인: `tail -100 ~/.claude/logs/md2html.log`
2. 제외 패턴/시스템 파일 매칭 여부 확인 (`system file`, `excluded path` 메시지)
3. 훅 직접 호출 테스트:
   ```bash
   echo '{"tool_name":"Write","tool_input":{"file_path":"/abs/path/file.md"}}' \
     | MD2HTML_DEBUG=1 CLAUDE_PLUGIN_ROOT=/path/to/plugin \
       bash /path/to/plugin/hooks/md2html-auto.sh
   ```
4. `jq` 설치 확인: `which jq`
5. 플러그인 활성화 확인: `/plugin` 명령으로 상태 점검

**다른 테마로 다시 변환하려면**
세션 안에서 "이 파일을 `<테마>` 로 다시 변환해줘" 라고 요청하거나 CLI 로:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/md2html.py file.md -t release -o file.html
```

**훅을 일시 비활성화**
```bash
MD2HTML_SKIP=1 claude
```

**.html 을 절대 직접 편집하지 마라**
원본은 `.md`. `.html` 은 매번 덮어써진다.

## 제거

```bash
/plugin uninstall md2html
```

## 라이선스

MIT
