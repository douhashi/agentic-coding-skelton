#!/usr/bin/env python3
"""ドキュメントの書式契約を検査する。

書式の定義（＝この検査が守る対象）は docs/document_system/templates/ にある。
検査対象は「放置すると必ず膨らむ」2 種類に絞る:

  - 各ディレクトリの INDEX.md      … 経路案内。内容の要約でも設計の記録でもない
  - roadmap.md                    … 時系列の計画。実装の記録を溜めない

依存はゼロ（Python 3 標準ライブラリのみ）。開発環境の有無に関わらず走る。
使い方:  python3 scripts/check-docs-format.py [docs ディレクトリ]
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

# 1 行の上限。日本語 1 文字 ≒ 3 バイトなので目安 60〜65 文字。
# 一次ルールは「1 行 1 文」で、これはその機械検査用の backstop。
MAX_LINE_BYTES = 200

# INDEX.md の 2 行目に許すラベル（固定語。自由記述にすると検査が長さだけになる）。
INDEX_DETAIL_LABEL = "  - 読むとき: "

# メタ文書はディレクトリではなく規約そのものなので INDEX.md を持たない。
EXEMPT_DIR_NAMES = {"document_system"}

# roadmap の見出しとして許す形。機能軸のグルーピングを作らせない。
ROADMAP_TOP_HEADINGS = {"## 予定（上から着手順）", "## 完了"}


@dataclass
class Violation:
    path: Path
    line_no: int
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line_no}: {self.message}"


def _too_long(line: str) -> int | None:
    n = len(line.encode("utf-8"))
    return n if n > MAX_LINE_BYTES else None


def check_index(path: Path) -> list[Violation]:
    """INDEX.md がテンプレートに従うか検査する。

    エントリ名が同ディレクトリに実在することを要求するのが最も強い制約で、
    これにより「実装層の説明」「設計判断」を書く場所が構造的に存在しなくなる。
    """
    out: list[Violation] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    listed: list[str] = []
    prev_was_entry = False

    for i, line in enumerate(lines, start=1):
        if (n := _too_long(line)) is not None:
            out.append(Violation(path, i, f"1 行 {n} バイト（上限 {MAX_LINE_BYTES}）"))

        if line.startswith("- `"):
            end = line.find("`", 3)
            if end == -1 or not line[end + 1 :].startswith(": "):
                out.append(Violation(path, i, "エントリの書式が `- `<file>`: <説明>` でない"))
            else:
                listed.append(line[3:end])
            prev_was_entry = True
            continue

        if line.startswith("  - "):
            if not prev_was_entry:
                out.append(Violation(path, i, "補足行がエントリの直後にない"))
            elif not line.startswith(INDEX_DETAIL_LABEL):
                out.append(Violation(path, i, f"補足行は `{INDEX_DETAIL_LABEL.strip()}` で始める"))
            prev_was_entry = False
            continue

        prev_was_entry = False
        if line.strip() == "" or line.startswith("# "):
            continue
        out.append(Violation(path, i, "エントリ・補足・見出し・空行以外は書かない"))

    # エントリ名 ⇔ 実在ファイルの双方向一致
    directory = path.parent
    actual = {
        p.name + ("/" if p.is_dir() else "")
        for p in directory.iterdir()
        if p.name != "INDEX.md" and not p.name.startswith(".")
    }
    for name in listed:
        if name not in actual:
            out.append(Violation(path, 0, f"エントリ `{name}` に対応するファイルが存在しない"))
    for name in sorted(actual - set(listed)):
        out.append(Violation(path, 0, f"`{name}` が INDEX.md に列挙されていない"))
    if len(listed) != len(set(listed)):
        out.append(Violation(path, 0, "エントリが重複している"))

    return out


def check_roadmap(path: Path) -> list[Violation]:
    """roadmap.md がテンプレートに従うか検査する。

    項目行の下に入れ子を作らせないのが本体。書ける場所が無いこと自体が、
    実装の記録が流れ込むのを防ぐ（規約の文章より強い）。
    """
    out: list[Violation] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    ids: list[str] = []

    for i, line in enumerate(lines, start=1):
        if (n := _too_long(line)) is not None:
            out.append(Violation(path, i, f"1 行 {n} バイト（上限 {MAX_LINE_BYTES}）"))

        if line.startswith("- ["):
            if line[3:5] not in ("x]", " ]", "~]"):
                out.append(Violation(path, i, "状態は [x] / [ ] / [~] のいずれか"))
            if line.startswith("- [x]") and "[dep " in line:
                out.append(Violation(path, i, "完了項目に [dep …] を残さない"))
            if (start := line.find("**")) != -1 and (end := line.find("**", start + 2)) != -1:
                ids.append(line[start + 2 : end])
            else:
                out.append(Violation(path, i, "項目 ID（**<ID>**）が無い"))
            continue

        if line.startswith("  ") and line.strip().startswith("- "):
            out.append(Violation(path, i, "項目行の下に入れ子を作らない（実装の記録は書かない）"))
            continue

        if line.startswith("## ") and line not in ROADMAP_TOP_HEADINGS:
            allowed = " / ".join(sorted(ROADMAP_TOP_HEADINGS))
            out.append(Violation(path, i, f"`## ` 見出しは {allowed} のみ"))
        if line.startswith("### "):
            label = line[4:].strip()
            ok = len(label) == 7 and label[4] == "-" and label[:4].isdigit() and label[5:].isdigit()
            if not ok:
                out.append(Violation(path, i, "`### ` 見出しは時間軸（YYYY-MM）のみ"))

    for name in sorted({x for x in ids if ids.count(x) > 1}):
        out.append(Violation(path, 0, f"項目 ID `{name}` が重複している"))

    return out


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent / "docs"
    if not root.is_dir():
        print(f"docs ディレクトリが見つかりません: {root}", file=sys.stderr)
        return 1

    violations: list[Violation] = []
    checked = 0

    for index in sorted(root.rglob("INDEX.md")):
        if any(part in EXEMPT_DIR_NAMES for part in index.parts):
            continue
        violations += check_index(index)
        checked += 1

    for directory in sorted(root.iterdir()):
        if not directory.is_dir() or directory.name in EXEMPT_DIR_NAMES:
            continue
        if (index := directory / "INDEX.md").exists():
            continue
        violations.append(Violation(index, 0, "ディレクトリに INDEX.md が無い"))

    roadmap = root / "development" / "roadmap.md"
    if roadmap.exists():
        violations += check_roadmap(roadmap)
        checked += 1

    if violations:
        for v in violations:
            print(str(v), file=sys.stderr)
        where = "docs/document_system/templates/"
        print(f"\n{len(violations)} 件の書式違反（書式の定義は {where}）", file=sys.stderr)
        return 1

    print(f"docs format: {checked} ファイル OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
