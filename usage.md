# md2html.py 사용법

KSAdmin top.html 의 md2html 위젯(`module/ksadmin/skin/basic/js/md2html.js`)을 Python 단일 파일로 포팅한 변환기. Markdown 파일을 10가지 컨셉 테마(인라인 CSS) HTML 문서로 변환한다.

## 요구사항

- **Python 3.6 이상** (3.7+ 권장)
- **외부 의존성** — 표준 라이브러리만 사용 (`argparse`, `html`, `os`, `re`, `sys`, `dataclasses`, `typing`)
  - 단, `dataclasses` 는 Python 3.6 표준에 없어 백포트가 필요하다.
  - `pip install -r requirements.txt` 를 실행하면 3.6 환경에서만 PyPI 백포트가 설치되고 3.7+ 에서는 자동 스킵된다.
  - 수동 설치: `pip install dataclasses` (3.6 한정)

## 다른 환경으로 옮길 때

`md2html.py` 한 파일만 복사하면 끝이다. 같은 디렉토리에 `requirements.txt` / `usage.md` 를 함께 둘 수도 있지만 동작에는 영향 없다.

```bash
# 옵션 A: 파일 한 개만 복사
scp /home/sjlee4628/md2html/md2html.py user@host:/some/path/

# 옵션 B: 디렉토리 통째로
rsync -av /home/sjlee4628/md2html/ user@host:/some/path/md2html/
```

## 기본 사용

```bash
python3 md2html.py <마크다운파일> [-t 테마]
```

- 출력 경로를 생략하면 **입력 .md 파일과 같은 디렉토리에 같은 이름의 .html** 파일을 생성한다.
- 테마를 생략하면 기본값 `meeting`(회의록)이 적용된다.

```bash
# 기본(회의록)
python3 md2html.py meeting-notes.md
# → meeting-notes.html 생성

# 다른 테마
python3 md2html.py release-2025q2.md -t release
python3 md2html.py release-2025q2.md -t 릴리즈노트   # 한글 별칭도 가능

# stdout 으로
python3 md2html.py meeting-notes.md --stdout > out.html

# stdin → stdout
cat meeting-notes.md | python3 md2html.py -t notice
```

## CLI 옵션

| 옵션               | 설명                                                                       |
| ------------------ | -------------------------------------------------------------------------- |
| `input` (위치인자) | Markdown 파일 경로. 생략 시 stdin 에서 읽음                                |
| `-t, --theme`      | 테마 ID 또는 한글 이름. 기본값 `meeting`                                   |
| `-o, --output`     | HTML 출력 경로. 생략 시 입력 디렉토리에 자동 생성 (stdin 입력 시 stdout)   |
| `--title`          | 문서 `<title>`. 생략 시 입력 파일명 사용                                   |
| `--lang`           | `<html lang>` 값. 기본값 `ko`                                              |
| `--stdout`         | 파일 입력이어도 결과를 stdout 으로 출력 (`-o` 보다 우선)                   |
| `--list-themes`    | 지원 테마 목록을 출력하고 종료                                             |

## 지원 테마 (10종)

| ID          | 한글 이름   | 별칭(CLI 인식)             | 특징                                   |
| ----------- | ----------- | -------------------------- | -------------------------------------- |
| `white`     | White       | `White`                    | 화이트/파란 액센트, 산세리프           |
| `dark`      | Dark        | `Dark`                     | VS Code 다크 톤, 청록 링크             |
| `release`   | 릴리즈 노트 | `릴리즈`, `릴리즈노트`     | 다크 헤더 + RELEASE 라벨, 시안 액센트  |
| `meeting`   | 회의록      | `회의록` *(기본값)*        | 안건/결정사항 강조, 청색 톤            |
| `report`    | 업무보고    | `업무보고`                 | 데이터 위주, 표 강조, 절제된 흑백 톤   |
| `proposal`  | 제안서      | `제안서`                   | 임팩트 표지, 진한 푸른 그라데이션      |
| `manual`    | 매뉴얼      | `매뉴얼`                   | 기술 문서, 다크 코드블록, 알림 박스    |
| `notice`    | 공지사항    | `공지사항`                 | 강한 빨강 헤더, 노랑 강조              |
| `plan`      | 기획안      | `기획안`                   | 보라 메인, 섹션 자동 번호              |
| `quotation` | 견적서      | `견적서`                   | 비즈니스 그린, 표 우측 정렬(금액)      |

## 지원 마크다운 문법

- ATX 헤딩(`# ~ ######`), Setext 헤딩(`===`, `---`)
- 단락, 하드 라인브레이크(트레일링 공백 2개 또는 `\` 줄바꿈)
- **굵게**(`**`, `__`), *기울임*(`*`, `_`), `인라인 코드`(`` ` ``), ~~취소선~~(`~~`)
- 링크 `[text](url "title")`, 오토링크 `<url>`, 이미지 `![alt](src "title")`
- 순서 없는/있는 리스트, 들여쓰기로 중첩
- 인용(`>`), 중첩 인용
- 펜스 코드블록(``` ``` ``` 또는 `~~~`), 들여쓰기 코드블록(4칸)
- 가로줄(`---`, `***`, `___`)
- 파이프 표(`:---:`, `---:`, `:---` 정렬 지원)

## Python 라이브러리로 사용

```python
from md2html import convert, convert_document, resolve_theme, THEMES, PRESETS

# 본문 fragment 만
fragment_html = convert("# 안녕\n\n**굵게** 텍스트")

# 전체 문서 (인라인 CSS 포함)
full_html = convert_document(
    "# 회의\n\n- 안건 1\n- 안건 2",
    title="2026-05 정기회의",
    lang="ko",
    theme="meeting",   # 또는 "회의록"
)

# 테마 ID 정규화
theme_id = resolve_theme("릴리즈 노트")  # → "release"
```
