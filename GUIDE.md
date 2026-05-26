# md2html — 배포용 사용법·적용·제작기

`.md` 파일을 작성/수정할 때마다 같은 디렉토리에 `.html` 이 자동으로 생기는 Claude Code 플러그인이다. 본 문서 한 장으로 **무엇인지 → 어떻게 만들어졌는지 → 어떻게 적용하는지 → 어떻게 쓰는지** 까지 다룬다.

---

## 1. 무엇인가

- **목적**: 사내 표준 디자인 10종으로 Markdown 을 깔끔한 단일 HTML(인라인 CSS) 로 즉시 변환한다.
- **형태**: 두 개의 산출물.
  - `md2html.py` — Python 단일 파일 CLI 변환기. 외부 의존성 0 (표준 라이브러리만).
  - `plugin/` — Claude Code 플러그인. PostToolUse 훅이 `Write`/`Edit`/`MultiEdit` 결과 `.md` 를 같은 디렉토리에 `.html` 로 자동 변환한다.
- **모태**: KSAdmin `top.html` 의 `md2html.js` 위젯(`module/ksadmin/skin/basic/js/md2html.js`)을 Python 으로 포팅하면서, 테마 10종을 그대로 보존했다.

### 핵심 동작 한 줄 요약

```
Claude 가 .md 작성/수정
  → PostToolUse 훅 발화
  → md2html.py 실행
  → 같은 이름의 .html 생성
```

### 특징

| 항목 | 내용 |
|---|---|
| 자동 변환 | `Write`/`Edit`/`MultiEdit` 결과에 한해 발화. 명시적 명령 불필요 |
| 자기완결 | `md2html.py` 가 플러그인에 번들. `pip install` 0개 |
| 테마 10종 | manual(기본) / meeting / white / dark / release / report / proposal / notice / plan / quotation. 한글 별칭 지원 |
| 안전 제외 | `CLAUDE.md`, `README.md`, `.git`, `node_modules`, `dist`, `build`, `.venv` 등 자동 스킵 |
| 비차단 | 변환 실패해도 Claude 작업을 막지 않음 (훅은 항상 `exit 0`) |
| 수동 보완 | `md2html` 스킬로 일괄 변환, 테마 재변환, 제외 우회 강제 변환 가능 |

---

## 2. 어떻게 만들어졌나

KSAdmin 위젯의 JS 포팅에서 출발해 **단일 파일 CLI → Claude Code 자동화 플러그인 → 마켓플레이스 등록 → 호환성 보강** 순으로 단계별 진화했다. 커밋 히스토리가 그대로 제작 노트다.

### 2.1 1단계 — 변환기 + 플러그인 초안 (`c100d7d`)

세 가지가 한 커밋으로 묶여 들어갔다.

1. **변환기 (`md2html.py`)** — 표준 라이브러리만으로 10종 테마(인라인 CSS) Markdown → HTML 변환 구현. 외부 의존성 0.
2. **Claude Code 플러그인 (`plugin/`)**
   - `hooks/md2html-auto.sh` — PostToolUse 발화 시 stdin JSON 을 `jq` 로 파싱해 `tool_name`/`file_path` 추출 → 확장자/제외 규칙 검사 → `md2html.py` 실행.
   - `scripts/md2html.py` — 변환기 번들. 훅이 `${CLAUDE_PLUGIN_ROOT}/scripts/md2html.py` 를 1순위로 탐색.
   - `skills/md2html/SKILL.md` — 일괄 변환·테마 재변환·강제 변환·로그 조회를 수동으로 보완.
3. **로컬 테스트 환경 (`.claude/`)** — 플러그인과 동일한 훅/스킬을 `${CLAUDE_PROJECT_DIR}` 기준으로 등록해, 설치 없이 저장소 안에서 바로 테스트할 수 있게 했다.

설계 시 결정한 원칙:

- **비차단**: 훅은 무슨 일이 있어도 `exit 0`. 변환 실패가 Claude 작업을 막지 않는다.
- **idempotent 출력**: 입력 `.md` 가 단일 진실 원본. `.html` 은 매번 덮어쓰는 파생 산출물.
- **제외 규칙 코드화**: 시스템 메타 파일(`CLAUDE.md`, `README.md`, `SKILL.md`, ...) 과 빌드 디렉토리(`.git`, `node_modules`, `dist`, `build`, `.venv`, ...) 는 훅·스킬이 같은 규칙으로 스킵.
- **확장 가능성**: `MD2HTML_SCRIPT` 로 외부 변환기 경로를 오버라이드할 수 있어, 번들과 별도 위치 양쪽 모두 지원.

### 2.2 2단계 — 마켓플레이스 등록 (`f78ab8f`)

`/plugin install <local>` 방식이 아닌 **한 줄 설치**(`/plugin marketplace add <repo>` → `/plugin install md2html`) 를 위해 저장소 루트에 `.claude-plugin/marketplace.json` 을 추가. 플러그인 소스는 `./plugin` 서브디렉토리로 지정해 기존 구조를 유지했다.

### 2.3 3단계 — 훅 로드 실패 수정 (`b7d282d`, `dcf9583`)

마켓플레이스로 배포된 첫 사용자 환경에서 다음 오류로 훅이 로드되지 않았다.

```
Failed to load hooks from .../hooks/hooks.json
expected: "record", path: ["hooks"]
```

원인: `settings.json` 의 모양을 잘못 차용해 `PostToolUse` 가 최상위에 노출되어 있었다. 플러그인 `hooks.json` 은 최상위 `"hooks"` 키로 한 번 더 감싸야 한다.

```json
{ "hooks": { "PostToolUse": [...] } }
```

공식 플러그인(`superpowers`, `security-guidance`) 의 매니페스트를 참고해 스키마를 맞췄다. 이어 `dcf9583` 에서 plugin version 을 `1.0.0 → 1.0.1` 로 올려 마켓플레이스 캐시 무효화를 트리거(동일 버전에서는 갱신이 안 됨).

### 2.4 4단계 — Python 3.6 호환 (`11ce74f` v1.0.2)

운영 서버 일부가 Python 3.6 이었다. 두 가지가 진입 장벽:

1. `from __future__ import annotations` — 3.6 `SyntaxError`
2. `from dataclasses import ...` — 3.6 `ModuleNotFoundError`

조치:

- `from __future__ import annotations` 제거. 모든 타입 힌트가 정의보다 뒤에서만 참조되어 forward reference 가 없으므로 즉시 evaluation 으로 충분.
- `requirements.txt` 에 환경 마커로 3.6 에서만 백포트가 깔리게: `dataclasses; python_version < "3.7"`.
- 회귀 검증(Python 3.12): `sample.md` 산출물이 변경 전후 **byte-단위 동일**, 10개 테마·한글 별칭·라이브러리 import 모두 정상.

### 2.5 5단계 — `re.Match` 타입 힌트 회귀 (`bb8c8c3` v1.0.3)

`re.Match`/`re.Pattern` 은 **Python 3.8 부터** 공식 추가된 타입이다. `from __future__ import annotations` 를 제거한 결과 모든 annotation 이 즉시 evaluate 되면서, 3.6/3.7 에서 `AttributeError: module 're' has no attribute 'Match'` 가 드러났다.

수정: 4곳의 `m: re.Match` → `m: "re.Match"` **string literal annotation**. 모든 버전에서 동작하며 정적 검사기는 그대로 인식한다. plugin/scripts/ 번들도 동일 적용, version → 1.0.3.

### 2.6 교훈

| 단계 | 교훈 |
|---|---|
| 1 | 훅·스킬·번들 변환기는 같은 제외 규칙을 코드 한 군데에서만 정의하지 말고 양쪽 모두에 갖춰야 한다 (`hook` 만으로는 일괄 작업·테마 재변환을 못 한다) |
| 2 | 마켓플레이스 매니페스트는 플러그인 매니페스트와 다른 스키마. 분리해서 다뤄야 한다 |
| 3 | 플러그인 `hooks.json` 은 settings.json 모양이 아니라 최상위 `"hooks"` 키로 감싸야 한다. 동일 버전은 캐시 갱신 안 됨 → 버전 bump 필요 |
| 4 | 환경 마커 (`; python_version < "3.7"`) 를 쓰면 한 `requirements.txt` 로 다중 버전을 지원할 수 있다 |
| 5 | `from __future__ import annotations` 를 제거할 때는 타입 객체의 도입 버전을 모두 확인해야 한다. 안전책은 의심 가는 타입을 string literal annotation 으로 바꾸는 것 |

---

## 3. 어떻게 적용하나 (설치/배포)

### 3.1 자가 설치 — 로컬 디렉토리에서

```bash
# 저장소 받기
git clone https://github.com/LaMelD/md2html.git
cd md2html

# Claude Code 안에서
/plugin install ./plugin
/reload-plugins
```

설치 후 **새 Claude Code 세션**부터 자동 동작한다.

### 3.2 자가 설치 — 마켓플레이스에서 한 줄 설치 (권장)

```text
/plugin marketplace add LaMelD/md2html
/plugin install md2html
```

저장소 루트의 `.claude-plugin/marketplace.json` 이 `./plugin` 을 가리키므로 사용자가 디렉토리 구조를 알 필요는 없다.

### 3.3 팀 배포 시나리오

| 시나리오 | 권장 방법 |
|---|---|
| 소수 머신 / 사내망 | 각자 `git clone` 후 `/plugin install ./plugin` |
| 다수 머신 / 외부망 OK | 마켓플레이스 매니페스트 활용 (`/plugin marketplace add ...`) |
| Python 3.6 환경 | 추가로 `pip install -r requirements.txt` 실행 (백포트 자동 설치) |
| CLI 만 필요 | `md2html.py` 한 파일만 복사 (3.4 절 참고) |

### 3.4 CLI 만 단독 사용

플러그인 없이 변환기만 두는 경우. 훅의 탐색 우선순위에 들어 있는 경로 중 하나에 두면 후속 플러그인 설치 시에도 자동으로 인식된다.

```bash
# 옵션 A — 사용자 로컬
mkdir -p "$HOME/.local/share/md2html"
cp md2html.py "$HOME/.local/share/md2html/md2html.py"

# 옵션 B — 시스템 공용
sudo mkdir -p /opt/md2html
sudo cp md2html.py /opt/md2html/md2html.py
```

### 3.5 의존성

- Python **3.6 이상** (3.7+ 권장)
  - 3.6 의 경우만 `dataclasses` 백포트 필요: `pip install -r requirements.txt`
- `bash` 4+
- `jq` (훅이 stdin JSON 파싱에 사용)

### 3.6 제거

```text
/plugin uninstall md2html
```

---

## 4. 어떻게 쓰나

### 4.1 자동 변환 (가장 흔한 케이스)

Claude Code 세션 안에서 평소처럼 `.md` 를 만들거나 고치면 끝이다. 같은 디렉토리에 같은 이름의 `.html` 이 자동 생성된다.

```
docs/release-2026q2.md   ← Claude 가 작성/수정
docs/release-2026q2.html ← 훅이 자동 생성 (덮어쓰기)
```

`.html` 은 직접 편집하지 않는다. 매번 덮어써진다.

### 4.2 수동 작업 (스킬)

훅이 처리하지 못하는 작업은 자연어로 요청하면 `md2html` 스킬이 처리한다.

| 요청 예시 | 동작 |
|---|---|
| "docs/ 폴더 전체를 release 테마로 일괄 변환해줘" | 일괄 변환 (제외 규칙 그대로 적용) |
| "README.md 도 white 테마로 변환해줘" | 제외 우회 강제 변환 |
| "이 파일을 dark 로 다시 변환" | 테마만 바꿔 재변환 |
| "최근 변환 로그 보여줘" | `~/.claude/logs/md2html.log` 조회 |
| "지원 테마 목록 알려줘" | `--list-themes` |

### 4.3 CLI 직접 사용

```bash
# 기본 — 같은 디렉토리에 .html 생성
python3 md2html.py docs/meeting-2026-05.md

# 테마 지정
python3 md2html.py docs/release-2026q2.md -t release
python3 md2html.py docs/release-2026q2.md -t 릴리즈노트   # 한글 별칭

# stdout
python3 md2html.py docs/meeting.md --stdout > out.html

# stdin → stdout
cat docs/notice.md | python3 md2html.py -t notice
```

옵션:

| 옵션 | 설명 |
|---|---|
| `input` (위치인자) | Markdown 파일 경로. 생략 시 stdin |
| `-t, --theme` | 테마 ID 또는 한글 이름. CLI 기본값 `meeting`, **훅 기본값 `manual`** |
| `-o, --output` | HTML 출력 경로. 생략 시 입력과 같은 디렉토리 |
| `--title` | 문서 `<title>` |
| `--lang` | `<html lang>` 값. 기본 `ko` |
| `--stdout` | 파일 입력이어도 stdout 으로 (`-o` 보다 우선) |
| `--list-themes` | 지원 테마 목록 출력 |

### 4.4 Python 라이브러리로 사용

```python
from md2html import convert, convert_document, resolve_theme, THEMES

fragment = convert("# 안녕\n\n**굵게** 텍스트")

full = convert_document(
    "# 회의\n\n- 안건 1\n- 안건 2",
    title="2026-05 정기회의",
    lang="ko",
    theme="meeting",   # 또는 "회의록"
)

theme_id = resolve_theme("릴리즈 노트")  # → "release"
```

### 4.5 테마 (10종)

| ID | 한글 | 별칭(CLI 인식) | 특징 |
|---|---|---|---|
| `white` | White | `White` | 화이트/파란 액센트, 산세리프 |
| `dark` | Dark | `Dark` | VS Code 다크 톤, 청록 링크 |
| `release` | 릴리즈 노트 | `릴리즈`, `릴리즈노트` | 다크 헤더 + RELEASE 라벨, 시안 액센트 |
| `meeting` | 회의록 | `회의록` | 안건/결정사항 강조, 청색 톤 (CLI 기본) |
| `report` | 업무보고 | `업무보고` | 데이터 위주, 표 강조, 절제된 흑백 |
| `proposal` | 제안서 | `제안서` | 임팩트 표지, 진한 푸른 그라데이션 |
| `manual` | 매뉴얼 | `매뉴얼` | 기술 문서, 다크 코드블록 (훅 기본) |
| `notice` | 공지사항 | `공지사항` | 강한 빨강 헤더, 노랑 강조 |
| `plan` | 기획안 | `기획안` | 보라 메인, 섹션 자동 번호 |
| `quotation` | 견적서 | `견적서` | 비즈니스 그린, 표 우측 정렬(금액) |

### 4.6 지원 마크다운 문법

- ATX 헤딩(`# ~ ######`), Setext 헤딩(`===`, `---`)
- 단락, 하드 라인브레이크(트레일링 공백 2개 또는 `\` 줄바꿈)
- **굵게**(`**`/`__`), *기울임*(`*`/`_`), `인라인 코드`, ~~취소선~~(`~~`)
- 링크 `[text](url "title")`, 오토링크 `<url>`, 이미지 `![alt](src "title")`
- 순서 있는/없는 리스트, 들여쓰기로 중첩
- 인용(`>`), 중첩 인용
- 펜스 코드블록(``` ``` ``` 또는 `~~~`), 들여쓰기 코드블록(4칸)
- 가로줄(`---`, `***`, `___`)
- 파이프 표(`:---:`, `---:`, `:---` 정렬 지원)

---

## 5. 제외 규칙

훅과 스킬이 동일하게 적용한다.

| 분류 | 패턴 |
|---|---|
| 시스템 파일 (basename) | `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `README.md`, `MEMORY.md`, `CHANGELOG.md`, `LICENSE.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SKILL.md` |
| 경로 패턴 | `*/.claude/*`, `*/.claude-plugin/*`, `*/.git/*`, `*/node_modules/*`, `*/memory/*`, `*/.venv/*`, `*/venv/*`, `*/dist/*`, `*/build/*`, `*/.next/*`, `*/.cache/*` |
| 기타 | 0 byte 파일, `.md`/`.markdown` 외 확장자 |

스킬을 통해 **명시 요청**하면 강제 변환된다.

---

## 6. 환경 변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `MD2HTML_SKIP` | (unset) | `1` 이면 훅 전체 비활성화 (긴급 우회) |
| `MD2HTML_THEME` | `manual` | 훅 기본 테마. ID 또는 한글 별칭 |
| `MD2HTML_SCRIPT` | (자동 탐색) | `md2html.py` 절대 경로 오버라이드 |
| `MD2HTML_PYTHON` | `python3` | Python 인터프리터 |
| `MD2HTML_LOG` | `~/.claude/logs/md2html.log` | 훅 로그 경로 |
| `MD2HTML_DEBUG` | (unset) | `1` 이면 상세 디버그 로그 |

세션 전체 기본 테마 변경:

```bash
export MD2HTML_THEME=release
claude
```

훅을 잠깐 끄고 싶을 때:

```bash
MD2HTML_SKIP=1 claude
```

### md2html.py 탐색 우선순위

훅은 다음 순서로 변환기를 찾는다.

1. `$MD2HTML_SCRIPT`
2. `${CLAUDE_PLUGIN_ROOT}/scripts/md2html.py` (번들)
3. `~/.local/share/md2html/md2html.py`
4. `~/md2html/md2html.py`
5. `/opt/md2html/md2html.py`

번들이 2순위이므로 기본 설치만으로 동작한다. 외부 위치의 최신본을 쓰고 싶을 때만 `MD2HTML_SCRIPT` 를 지정한다.

---

## 7. 트러블슈팅

### .md 를 저장해도 .html 이 안 생긴다

1. 로그 확인

   ```bash
   tail -100 ~/.claude/logs/md2html.log
   ```

2. 제외 규칙 매칭 여부 확인 (로그의 `system file`, `excluded path` 메시지).
3. 훅 직접 호출 테스트

   ```bash
   echo '{"tool_name":"Write","tool_input":{"file_path":"/abs/path/file.md"}}' \
     | MD2HTML_DEBUG=1 CLAUDE_PLUGIN_ROOT=/path/to/plugin \
       bash /path/to/plugin/hooks/md2html-auto.sh
   ```

4. `jq` 설치 확인: `which jq`
5. 플러그인 활성화 확인: Claude Code 안에서 `/plugin`

### 훅이 로드되지 않는다 (마켓플레이스 설치 후)

마켓플레이스 캐시가 묵었을 가능성. 저장소 측에서 `plugin.json` 의 `version` 을 올려 캐시 무효화. 사용자는 `/plugin` 으로 재설치한다.

### Python 3.6 에서 ImportError

`dataclasses` 백포트가 없어서 그렇다.

```bash
pip install -r requirements.txt
# 또는
pip install dataclasses
```

### .html 이 손으로 고친 내용을 잃었다

`.html` 은 **파생 산출물**이다. `.md` 만 편집하고, 결과 HTML 은 절대 직접 고치지 않는다.

---

## 8. 디렉토리 구조

```
md2html/
├── md2html.py                       # CLI 변환기 (단일 파일)
├── usage.md                         # CLI 사용법
├── sample.md                        # 데모 입력
├── INSTALL.md                       # 설치 가이드
├── GUIDE.md                         # ← 이 문서 (배포용 종합)
├── requirements.txt                 # 3.6 한정 dataclasses 백포트
├── .claude-plugin/marketplace.json  # 마켓플레이스 매니페스트
├── .claude/                         # 저장소 로컬 테스트용 훅/스킬
└── plugin/                          # Claude Code 플러그인
    ├── .claude-plugin/plugin.json
    ├── hooks/{hooks.json, md2html-auto.sh}
    ├── scripts/md2html.py           # 변환기 번들 (루트 사본)
    ├── skills/md2html/SKILL.md
    └── README.md
```

`plugin/scripts/md2html.py` 는 저장소 루트 `md2html.py` 의 사본이다. **변환기 업데이트 시 두 곳을 모두 동기화**한다.

---

## 9. 버전 이력

| 버전 | 커밋 | 요지 |
|---|---|---|
| 1.0.0 | `c100d7d` | 변환기 + 플러그인 + 스킬 + 로컬 테스트 환경 초안 |
| (개정) | `f78ab8f` | 저장소 루트에 marketplace.json 추가 |
| (개정) | `b7d282d` | `hooks.json` 을 최상위 `hooks` 키로 감싸 스키마 준수 |
| 1.0.1 | `dcf9583` | 마켓플레이스 캐시 무효화 (버전 bump) |
| 1.0.2 | `11ce74f` | Python 3.6 호환 (`from __future__` 제거, dataclasses 백포트) |
| 1.0.3 | `bb8c8c3` | `re.Match` 타입 힌트를 string literal 로 (3.6/3.7 회귀 수정) |

---

## 10. 라이선스

MIT
