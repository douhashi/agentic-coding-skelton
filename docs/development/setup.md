# 開発環境セットアップ

## 前提

[mise](https://mise.jdx.dev/) が入っていること。**それ以外のツールの版はすべて `mise.toml` が持つ**。

## 2 コマンド

```sh
mise install     # mise.toml の [tools] を入れる
mise run setup   # git hooks を導入し、開発を始められる状態にする
```

これで完了する。`mise run setup` は冪等なので何度実行してもよい。

新しい言語やツールを足すときは、`mise.toml` の `[tools]` に版を pin し、
導入手順を `[tasks.setup]` へ足す。**この 2 コマンドで環境が整う状態を保つ**
（手順書に「あれも入れてください」を書き足さない）。

## タスク

`mise tasks` で一覧できる。

| タスク | 内容 |
|---|---|
| `mise run setup` | git hooks の導入 |
| `mise run lint:docs` | ドキュメントの書式契約の検査 |
| `mise run check` | フルチェック（品質タスクをすべて束ねる） |

## 何が検査されるか

`mise run lint:docs` と pre-commit フックが `scripts/check-docs-format.py` を通す。
検査するのは、放置すると必ず膨らむ 2 種類だけである。

| 対象 | 主な検査 |
|---|---|
| 各 `INDEX.md` | 1 行の上限／エントリ書式／補足ラベルの固定／**エントリ名 ⇔ 実在ファイルの双方向一致**／散文の禁止 |
| `roadmap.md` | 1 行の上限／**入れ子の禁止**／完了項目に依存を残さない／課題番号の重複なし／見出しの制限 |

書式の定義は [`../document_system/templates/`](../document_system/templates/) にある。

検査器は **Python 3 標準ライブラリのみ**で動く。開発環境の有無に関わらず走らせられ、
言語やツールチェーンを増やしても影響を受けない。

## CI

CI は PR の変更範囲で実行内容を分ける。

| 変更範囲 | 実行 |
|---|---|
| `docs/` 配下のみ | `mise run lint:docs`（書式契約だけ） |
| それ以外を含む | `mise run check`（フルチェック） |

テストや検査を足すときは `mise.toml` の `[tasks.check]` の `depends` に加える。CI は変えない。
必須ステータスチェックには、どちらの分岐でも結果を返す `result` ジョブを指定する。

書式契約はレビューの目視ではなく、**機械的に落とす**（規約を文章で定めるだけでは守られない）。
