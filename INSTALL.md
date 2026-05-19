# md2html 저장소 사용 가이드

이 저장소는 두 가지 산출물을 담는다.

1. **`md2html.py`** — Markdown → HTML 변환기 CLI 단일 파일 (Python 표준 라이브러리만 사용)
2. **`plugin/`** — Claude Code 플러그인 (PostToolUse 훅으로 `.md` 작성/수정 시 자동 변환)

CLI 사용법은 `usage.md`, 플러그인 상세는 `plugin/README.md` 를 본다. 이 문서는 저장소 클론 직후 셋업 흐름만 다룬다.

## 빠른 시작

```bash
git clone https://github.com/LaMelD/md2html.git
cd md2html
```

이후 두 가지 사용 모드를 자유롭게 선택한다.

### 모드 A — CLI 변환기로만 쓰기

```bash
python3 md2html.py sample.md -t manual
# → sample.html 생성
```

요구사항: Python 3.7+. pip 설치 불필요.

### 모드 B — Claude Code 자동 변환 (권장)

Claude Code 세션 안에서 `plugin/` 을 설치한다.

```text
/plugin install ./plugin
/reload-plugins
```

새 Claude Code 세션을 열면 `Write`/`Edit`/`MultiEdit` 결과로 생긴 `.md` 가 같은 디렉토리에 `.html` 로 자동 변환된다 (기본 테마 `manual`).

플러그인의 환경변수·제외 규칙·트러블슈팅은 모두 `plugin/README.md` 에 정리되어 있다.

## 글로벌 배포

팀 또는 다른 머신에 배포하는 방법.

### 방법 1 — 로컬 디렉토리에서 직접 설치

각 머신에 저장소를 클론하고 `/plugin install <path>/plugin` 으로 등록한다.

### 방법 2 — marketplace 로 게시

이 저장소를 marketplace 로 등록한다.

```text
/plugin marketplace add LaMelD/md2html
/plugin install md2html
```

저장소가 plugin 디렉토리를 루트에 갖지 않으므로, 별도 marketplace 매니페스트(`.claude-plugin/marketplace.json`)를 추가하거나 plugin 디렉토리를 저장소 루트로 옮겨야 한다.

## CLI 직접 호출 (변환기만 필요한 경우)

플러그인 없이 `md2html.py` 만 별도 위치에 두고 쓰는 시나리오는 다음 경로 중 한 곳을 권장한다.

```bash
# 옵션 A: 사용자 로컬
mkdir -p "$HOME/.local/share/md2html"
cp md2html.py "$HOME/.local/share/md2html/md2html.py"

# 옵션 B: 시스템 공용
sudo mkdir -p /opt/md2html
sudo cp md2html.py /opt/md2html/md2html.py
```

플러그인 훅의 `find_script()` 가 이 경로들을 자동 탐색한다 (`plugin/README.md` 의 "md2html.py 탐색 우선순위" 참고).

## 환경변수 요약

플러그인 / CLI 양쪽 모두 다음을 인식한다.

| 변수 | 기본 | 설명 |
|------|------|------|
| `MD2HTML_SKIP` | (unset) | `1` 이면 플러그인 훅 비활성화 |
| `MD2HTML_THEME` | `manual` | 기본 테마 (`white` `dark` `release` `meeting` `report` `proposal` `manual` `notice` `plan` `quotation` 또는 한글 별칭) |
| `MD2HTML_SCRIPT` | (자동) | `md2html.py` 절대 경로 오버라이드 |
| `MD2HTML_PYTHON` | `python3` | Python 인터프리터 |
| `MD2HTML_LOG` | `~/.claude/logs/md2html.log` | 훅 로그 경로 |
| `MD2HTML_DEBUG` | (unset) | `1` 이면 디버그 로그 |

## 의존성

- Python 3.7+
- `bash` 4+
- `jq` (플러그인 훅이 stdin JSON 파싱에 사용)

## 트러블슈팅

플러그인 자동 변환이 동작하지 않거나 동작이 이상할 때는 `plugin/README.md` 의 트러블슈팅 섹션을 우선 참고한다. 핵심 진단 명령:

```bash
tail -100 ~/.claude/logs/md2html.log
```

## 디렉토리

```
md2html/
├── md2html.py              # CLI 변환기 (단일 파일)
├── usage.md                # CLI 사용법
├── sample.md               # 데모 입력
├── plugin/                 # Claude Code 플러그인
│   ├── .claude-plugin/plugin.json
│   ├── hooks/{hooks.json,md2html-auto.sh}
│   ├── scripts/md2html.py  # 번들 (저장소 루트 md2html.py 의 사본)
│   ├── skills/md2html/SKILL.md
│   └── README.md
└── INSTALL.md              # 이 문서
```

`plugin/scripts/md2html.py` 는 저장소 루트의 `md2html.py` 사본이다. 변환기 업데이트 시 두 곳을 모두 동기화한다.

## 라이선스

MIT
