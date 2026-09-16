# md2html

`.md` 파일을 작성하거나 수정하면 같은 디렉토리에 같은 이름의 `.html` 이 자동으로 생기는 Claude Code 플러그인이다. 변환기는 Python 표준 라이브러리만 쓰는 단일 파일이라 플러그인 없이 CLI 로도 쓴다.

| 산출물 | 역할 |
|---|---|
| `md2html.py` | Markdown → HTML 변환기. 외부 의존성 0, 테마 10종(인라인 CSS) |
| `plugin/` | Claude Code 플러그인. `Write`/`Edit`/`MultiEdit` 로 `.md` 가 바뀌면 PostToolUse 훅이 변환기를 실행 |

```text
Claude 가 .md 작성/수정 → PostToolUse 훅 → md2html.py → 같은 이름의 .html 생성
```

## 설치

### 1. Claude Code 플러그인 (권장)

Claude Code 세션 안에서 세 줄이면 끝난다.

```text
/plugin marketplace add LaMelD/md2html
/plugin install md2html
/reload-plugins
```

새 세션부터 자동으로 동작한다. 요구 사항은 Python 3.6 이상(3.7+ 권장), bash 4 이상, `jq` 다. Python 3.6 에서만 `pip install -r requirements.txt` 로 `dataclasses` 백포트를 추가한다.

### 2. 로컬 클론에서 설치

```bash
git clone https://github.com/LaMelD/md2html.git
cd md2html
```

```text
/plugin install ./plugin
/reload-plugins
```

### 3. CLI 만 쓰기

`md2html.py` 한 파일만 복사하면 된다. 아래 경로 중 하나에 두면 나중에 플러그인을 설치해도 훅이 자동으로 찾는다.

```bash
mkdir -p "$HOME/.local/share/md2html" && cp md2html.py "$HOME/.local/share/md2html/"
# 또는 시스템 공용: sudo mkdir -p /opt/md2html && sudo cp md2html.py /opt/md2html/
```

### 제거

```text
/plugin uninstall md2html
```

## 사용

### 자동 변환

설치 후에는 할 일이 없다. Claude Code 가 `.md` 를 저장할 때마다 옆에 `.html` 이 생기고, 다시 저장하면 덮어쓴다. `.md` 가 원본이고 `.html` 은 파생물이므로 `.html` 을 직접 고치지 않는다.

다음은 자동 변환에서 제외된다. 필요하면 세션 안에서 "README.md 도 white 테마로 변환해줘" 처럼 요청하면 `md2html` 스킬이 강제 변환한다.

- 메타 파일: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `README.md`, `MEMORY.md`, `CHANGELOG.md`, `LICENSE.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SKILL.md`
- 경로: `.claude/`, `.claude-plugin/`, `.git/`, `node_modules/`, `memory/`, `.venv/`, `venv/`, `dist/`, `build/`, `.next/`, `.cache/`
- 빈 파일, `.md`/`.markdown` 외 확장자

### 세션 안에서 수동 작업 (스킬)

- "docs/ 폴더 전체를 release 테마로 일괄 변환해줘"
- "이 파일을 dark 테마로 다시 변환"
- "최근 변환 로그 보여줘"
- "지원 테마 목록 알려줘"

### CLI

```bash
python3 md2html.py notes.md                  # notes.html 생성 (CLI 기본 테마: meeting)
python3 md2html.py notes.md -t release       # 테마 지정
python3 md2html.py notes.md -t 릴리즈노트     # 한글 이름도 인식
python3 md2html.py notes.md --stdout > out.html
cat notes.md | python3 md2html.py -t notice  # stdin → stdout
python3 md2html.py --list-themes
```

| 옵션 | 설명 |
|---|---|
| `input` | Markdown 파일 경로. 생략하면 stdin |
| `-t, --theme` | 테마 ID 또는 한글 이름. 기본 `meeting` (플러그인 훅의 기본은 `manual`) |
| `-o, --output` | 출력 경로. 생략하면 입력 파일 옆에 생성 |
| `--title` | 문서 `<title>`. 생략하면 입력 파일명 |
| `--lang` | `<html lang>`. 기본 `ko` |
| `--stdout` | 파일 입력이어도 stdout 으로 출력 |
| `--list-themes` | 테마 목록 출력 |

Python 에서 직접 부를 수도 있다.

```python
from md2html import convert, convert_document
fragment = convert("# 제목\n\n본문")                                   # 본문 조각만
page = convert_document("# 회의\n\n- 안건 1", title="정기회의", theme="회의록")  # 인라인 CSS 포함 전체 문서
```

### 테마

| ID | 이름 | 특징 |
|---|---|---|
| `manual` | 매뉴얼 (플러그인 기본) | 기술 문서, 다크 코드블록, 알림 박스 |
| `meeting` | 회의록 (CLI 기본) | 안건·결정사항 강조, 청색 톤 |
| `white` | White | 화이트, 파란 액센트 |
| `dark` | Dark | VS Code 다크 톤 |
| `release` | 릴리즈 노트 | 다크 헤더, RELEASE 라벨 |
| `report` | 업무보고 | 표 강조, 절제된 흑백 |
| `proposal` | 제안서 | 임팩트 표지, 푸른 그라데이션 |
| `notice` | 공지사항 | 빨강 헤더, 노랑 강조 |
| `plan` | 기획안 | 보라 메인, 섹션 자동 번호 |
| `quotation` | 견적서 | 비즈니스 그린, 금액 우측 정렬 |

### 환경 변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `MD2HTML_THEME` | `manual` | 훅의 기본 테마. 예: `export MD2HTML_THEME=release` 후 `claude` 실행 |
| `MD2HTML_SKIP` | (unset) | `1` 이면 훅 비활성화. 예: `MD2HTML_SKIP=1 claude` |
| `MD2HTML_SCRIPT` | (자동) | `md2html.py` 경로 오버라이드 |
| `MD2HTML_PYTHON` | `python3` | Python 인터프리터 |
| `MD2HTML_LOG` | `~/.claude/logs/md2html.log` | 훅 로그 경로 |
| `MD2HTML_DEBUG` | (unset) | `1` 이면 디버그 로그 |

## 문제 해결

`.md` 를 저장해도 `.html` 이 안 생기면 로그부터 본다.

```bash
tail -100 ~/.claude/logs/md2html.log
```

`system file` 이나 `excluded path` 가 찍혀 있으면 제외 규칙에 걸린 것이다. 아무것도 안 찍히면 `which jq` 로 jq 를 확인하고, `/plugin` 으로 플러그인이 활성화돼 있는지 본다. 훅을 직접 호출해 볼 수도 있다.

```bash
echo '{"tool_name":"Write","tool_input":{"file_path":"/abs/path/file.md"}}' \
  | MD2HTML_DEBUG=1 CLAUDE_PLUGIN_ROOT=/path/to/plugin bash /path/to/plugin/hooks/md2html-auto.sh
```

## 문서

- [GUIDE.md](GUIDE.md) — 설치·사용·제작기 종합 가이드
- [INSTALL.md](INSTALL.md) — 클론 직후 셋업과 팀 배포
- [usage.md](usage.md) — CLI 상세 (옵션, 지원 마크다운 문법, 라이브러리 API)
- [plugin/README.md](plugin/README.md) — 플러그인 동작 흐름, 제외 규칙, 탐색 우선순위, 트러블슈팅

## 구조

```text
md2html/
├── md2html.py                  # CLI 변환기 (단일 파일)
├── plugin/                     # Claude Code 플러그인
│   ├── .claude-plugin/plugin.json
│   ├── hooks/{hooks.json, md2html-auto.sh}
│   ├── scripts/md2html.py      # 루트 md2html.py 의 사본 (갱신 시 둘 다 수정)
│   └── skills/md2html/SKILL.md
├── .claude-plugin/marketplace.json
├── sample.md
└── requirements.txt            # Python 3.6 전용 dataclasses 백포트
```
