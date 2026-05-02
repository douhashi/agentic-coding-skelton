# Cloudflare CI デプロイ運用ガイド

GitHub Actions（または同等の CI）から Cloudflare Workers / D1 / R2 / Workflows をデプロイする際の汎用的な手順とハマりどころをまとめる。
プロジェクト固有の判断は別ドキュメント（例: `secrets-management.md`）に委ね、本書は **どのプロジェクトにも当てはまる土台** に絞る。

---

## 1. 全体像

CI からの Cloudflare デプロイは概念的に **3 層** に分かれる:

```
[シークレット一次ソース]   [CI 実行環境]                [Cloudflare 上の Worker ランタイム]
  Infisical / Doppler      GitHub Secrets                 wrangler secrets / vars / bindings
  1Password / Vault   →    (Actions runner の env)   →    (Worker process が読む env)
  人間が編集する場所       wrangler / curl 認証用         実行時に呼ばれる API キー類
```

役割:

| 層 | 何が入るか | 誰が読むか |
|---|---|---|
| 一次ソース | すべての secrets の真実の値 | 人間 + CI 同期スクリプト |
| GitHub Secrets | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` 等 CI で wrangler を動かすのに必要な最小値 | Actions runner |
| Worker ランタイム | Worker process が `env.X` で参照する API キー / 接続情報 | Worker 自身（リクエスト処理中） |

**CI が GH Secrets を読んで wrangler を実行 → wrangler が「Worker ランタイム secrets を Cloudflare に push」する**、というのが標準パターン。Worker は Infisical を直接読まない（レイテンシ・依存・コスト増を避ける）。

---

## 2. Cloudflare API Token に必要な権限

CI 用の API Token は Cloudflare ダッシュボードの **My Profile → API Tokens → Create Custom Token** で作成する。
最小権限の原則で、使うリソースに応じて以下を組み合わせる:

| 利用機能 | 必要な permission | 備考 |
|---|---|---|
| Workers のデプロイ | **Account → Workers Scripts: Edit** | 全プロジェクトで必須 |
| Worker secrets の `wrangler secret put/bulk` | **Account → Workers Scripts: Edit** | 同上に含まれる |
| D1 の作成 / migration 適用 | **Account → D1: Edit** | `wrangler d1 create` / `migrations apply --remote` で必須 |
| R2 bucket の作成 / CORS / lifecycle 設定 | **Account → Workers R2 Storage: Edit** | `wrangler r2 bucket *` で必須 |
| Workflows のデプロイ | **Account → Workers Scripts: Edit** | Workflows は Worker の class export として扱われるので Workers Scripts 権限で足りる |
| Queues / Durable Objects | **Account → Workers Scripts: Edit** | 同上 |
| KV namespace の操作 | **Account → Workers KV Storage: Edit** | KV を使う場合のみ |
| Pages | **Account → Cloudflare Pages: Edit** | Pages を使う場合のみ |

### Account Resources

- **Include - All accounts** か **個別アカウント指定** のどちらでも可
- 複数アカウントを所有する個人/組織は個別指定が無難

### TTL

- **No expiration** または十分長い期限（CI が突然動かなくなる事故を避ける）
- 期限切れエラーは静かに deploy job の途中で発生するので、**期限を Calendar / Slack reminder で監視する** 運用にしておく

### Token のローテーション

- Cloudflare は **token の値そのものを後から取得できない**（作成時の 1 回しか表示されない）
- 既存 token に scope を追加するときは **Edit → permission を足す → Update Token** で **token 値は維持される**（GH Secrets 側の更新不要）
- Roll（再発行）した場合のみ新値を一次ソース → GH Secrets に伝搬

### よくある失敗

- **D1:Edit が無いまま `wrangler d1 create` を呼ぶ → `code:10000 Authentication error`**
- **R2:Edit が無いまま `wrangler r2 bucket cors set` を呼ぶ → 403**
- どちらも token が無効に見えるエラーが出るが、実態は **scope 不足**。token を再発行するのではなく **既存 token に scope 追加** が正解

---

## 3. CI で使う GitHub Secrets

CI runner で wrangler を動かすために最低限必要なもの:

| Secret 名 | 用途 |
|---|---|
| `CLOUDFLARE_API_TOKEN` | wrangler 全コマンドの認証 |
| `CLOUDFLARE_ACCOUNT_ID` | account-scoped API 呼び出しの宛先指定 |

これら 2 つは **wrangler が env から自動で読む** 慣習。`wrangler.jsonc` にも書ける（`account_id`）が、CI では env 経由が標準。

その他の secrets（R2 access key / 外部 API key 等）は **GH Secrets に置く必要が必ずしも無い**。一次ソース（Infisical 等）から直接 wrangler 経由で Worker secrets に同期できれば、GH Secrets を経由する必要はない。

### Infisical 等の外部マネージャーを使う場合

| 経路 | 例 |
|---|---|
| 外部マネージャー → GH Secrets（自動同期） | Infisical Native Integration / Doppler GitHub Sync 等 |
| 外部マネージャー → CI 実行時に env 注入（GH Secrets を経由しない） | `infisical run --env=prod -- pnpm deploy` のように runner 上で直接展開 |

**GH Secrets 経由のメリット**: 動作確認が簡単、actions/checkout のキャッシュ層と相性が良い。
**直接注入のメリット**: GH Secrets の値を自動的に最新化できる、 secrets が GitHub 側に残らない。

どちらでも良いが、**両方を併用しない**（同期方向が二重になり値の食い違いの原因）。

---

## 4. Worker ランタイム secrets（wrangler secret）

Worker process が `env.X` で読む値。`wrangler.jsonc` の `vars` に書くと **平文がリポジトリにコミットされる**ため、**機密値は必ず `wrangler secret` で投入** する。

### 個別投入

```bash
echo "<value>" | wrangler secret put MY_KEY
```

### bulk 投入（推奨）

```bash
wrangler secret bulk secrets.json
```

`secrets.json` の形式:

```json
{
  "API_KEY": "xxx",
  "DATABASE_URL": "yyy",
  "R2_ACCESS_KEY_ID": "zzz"
}
```

- 一度に複数投入できるので CI 同期スクリプトに向く
- 既存 secret は上書きされる
- 削除は別途 `wrangler secret delete <KEY>` が必要（bulk では削除されない）

### vars と secrets の使い分け

| 用途 | 置き場所 |
|---|---|
| 公開しても問題ない設定値（モード切替、URL 等） | `wrangler.jsonc` の `vars` |
| API キー / DB クレデンシャル / トークン | `wrangler secret`（リポジトリに値を入れない） |

### 確認コマンド

```bash
wrangler secret list   # 現在 push 済みの secret 名一覧（値は見れない）
```

---

## 5. CI ワークフロー（最小構成）

GitHub Actions の `deploy.yml` 例（汎用版）:

```yaml
name: Deploy

on:
  push:
    branches: [main]
  workflow_dispatch: {}

permissions:
  contents: read
  deployments: write   # GitHub Deployments に履歴を残すため

concurrency:
  group: deploy-${{ github.ref }}
  cancel-in-progress: false   # デプロイ中の中断は中途半端な状態を残すので避ける

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://your-worker.example.workers.dev
    steps:
      - uses: actions/checkout@v4

      # Node / pnpm 等のセットアップ（mise / asdf / setup-node などプロジェクトに応じて）
      - uses: jdx/mise-action@v2
        with: { install: true, cache: true }

      - name: Install dependencies
        run: pnpm install --frozen-lockfile

      # 品質ゲート（PR で既に走っているとしても、main 直 push の保険として再実行する）
      - name: Lint / Typecheck / Test
        run: |
          pnpm lint
          pnpm typecheck
          pnpm test

      # D1 を使うなら migration を build 前に適用
      - name: Apply D1 migrations (remote)
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
        run: pnpm wrangler d1 migrations apply <db-name> --remote

      # Worker secrets の同期（外部マネージャーから取得 → bulk 投入する例）
      - name: Sync Worker secrets
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
        run: |
          # 一次ソースから JSON を生成（Infisical の例）
          # infisical secrets list --env=prod --plain --format=json > secrets.json
          pnpm wrangler secret bulk secrets.json
          rm -f secrets.json   # runner 上のディスクに残さない

      - name: Deploy
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
        run: pnpm run deploy   # opennextjs-cloudflare deploy / wrangler deploy 等

      - name: Smoke test
        env:
          APP_URL: https://your-worker.example.workers.dev
        run: |
          set -euo pipefail
          # Cloudflare edge 伝搬を待つループ（最大 60s）
          for i in $(seq 1 12); do
            code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 "$APP_URL/" || echo "000")
            echo "attempt $i: HTTP $code"
            [ "$code" = "200" ] && exit 0
            sleep 5
          done
          exit 1
```

### 設計上のポイント

- **`cancel-in-progress: false`**: デプロイ中の中断は中途半端な状態を作るので避ける。同時並行 push は後続を待たせる
- **`environment: production`**: GitHub の **Deployments** タブで「いつ・誰のコミットがデプロイされたか」が一覧化される（履歴可視化）
- **品質ゲートの再実行**: PR で通っていても main 直 push（管理者権限）や squash merge による差分発生に備えた保険
- **smoke test のリトライ**: deploy API が 200 を返した直後でも edge 伝搬が数秒〜数十秒遅れることがあるため、待機ループを内包
- **Worker secrets の同期は deploy より先**: deploy → secret 投入の順だと、新しい Worker コードが古い secret 値で動く瞬間が発生する。**migrations → secrets → deploy** の順が安全

### ロールバック

| 方法 | やり方 | 速度 |
|---|---|---|
| revert PR | 直前のコミットを revert する PR を作って main にマージ | 5 分（次回デプロイで反映） |
| GH Actions の re-run | 過去の成功 deploy を Actions タブから Re-run | 数分（コードはその時点に戻る） |
| `wrangler rollback` | wrangler 5+ で Worker version を戻す | 即時（ただしコード/CI 履歴と乖離する） |

通常は **revert PR を最優先**（CI 履歴と Worker 状態が一致する）。

---

## 6. R2 を直接アップロード経路で使う場合

ブラウザから R2 へ直接 PUT する設計（presigned URL 方式）では、**R2 bucket の CORS 設定** が必須。これを忘れるとブラウザのリクエストが pre-flight で失敗する。

### CORS 設定

```bash
wrangler r2 bucket cors set <bucket-name> --file cors.json --force
```

`cors.json`:

```json
{
  "rules": [
    {
      "allowed": {
        "origins": ["https://your-app.example.com", "http://localhost:3000"],
        "methods": ["PUT", "GET", "HEAD"],
        "headers": ["*"]
      },
      "exposeHeaders": ["ETag"],
      "maxAgeSeconds": 3600
    }
  ]
}
```

- `origins` は **完全一致**（ワイルドカードは使えない）。複数環境（prod / dev / localhost）を全部列挙する
- `methods` は使う動詞だけに絞る（`PUT` のみで十分なら他は外す）
- `exposeHeaders: ["ETag"]` は multipart upload で必要になることがある

### presigned URL の発行

Worker から発行する場合、**aws4fetch** を使うのが最軽量:

```ts
import { AwsClient } from "aws4fetch";

const client = new AwsClient({
  accessKeyId: env.R2_ACCESS_KEY_ID,
  secretAccessKey: env.R2_SECRET_ACCESS_KEY,
  service: "s3",
  region: "auto",
});

const endpoint = `${env.R2_ENDPOINT.replace(/\/$/, "")}/${env.R2_BUCKET}`;
const url = new URL(`${endpoint}/${key}`);
url.searchParams.set("X-Amz-Expires", String(900));  // 15 分
const signed = await client.sign(new Request(url, { method: "PUT" }), {
  aws: { signQuery: true },
});
return signed.url;
```

### R2 接続情報の取得元

| 値 | 取得方法 |
|---|---|
| `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | Cloudflare ダッシュボード → R2 → **Manage R2 API tokens** で発行 |
| `R2_ENDPOINT` | `https://<account_id>.r2.cloudflarestorage.com`（account 固定） |
| `R2_BUCKET` | bucket 名 |

`R2_ACCOUNT_ID` を別途持つ必要はない（`R2_ENDPOINT` に含まれる）。コードを書くときは **endpoint を渡す方が柔軟**（jurisdictional endpoint への切替も同じ変数で対応できる）。

---

## 7. ローカル開発と prod の差分

`wrangler dev`（miniflare ベースのローカル実行）は **本番では動くが local では動かない bindings** がある:

| Binding | local 動作 | 備考 |
|---|---|---|
| D1 | ローカル SQLite で動く | `--local` で local DB、`--remote` で本番 DB |
| R2 | ローカルファイルで動く | object 操作は本物と同等のインターフェース |
| KV | ローカルストアで動く | |
| Durable Objects | ローカルで動く | |
| **Workflows** | **動かない** | wrangler が `These are not available in local development` と警告。production 専用 |
| Queues | 部分的に動く | producer は OK、consumer は制限あり |
| Email Workers | 動かない | production 専用 |

### CI / Playwright での E2E

- **mock mode**: ローカル wrangler dev で完結。bindings 不要 or in-memory で代替
- **real mode (本番疎通)**: Workflows / Email を使う場合は **production URL に対してテスト** する必要がある。Playwright config で `BASE_URL` で切り替え可能にしておくと運用が楽:

  ```ts
  const baseURL = process.env.BASE_URL ?? `http://localhost:${PORT}`;
  const useExternalServer = !!process.env.BASE_URL;

  export default defineConfig({
    use: { baseURL },
    webServer: useExternalServer ? undefined : { /* local server */ },
  });
  ```

  `BASE_URL=https://prod.example.com pnpm test:e2e` で prod に対して走らせる。

---

## 8. デプロイ前の初期セットアップ手順

新規プロジェクトでこの順に 1 度だけ実行する:

1. **Cloudflare API Token 作成**: 必要 scope を含めて発行 → 一次ソース（Infisical 等）に保存
2. **D1 database 作成**:
   ```bash
   wrangler d1 create <db-name>
   ```
   返ってきた `database_id` を `wrangler.jsonc` に書く
3. **R2 bucket 作成**:
   ```bash
   wrangler r2 bucket create <bucket-name>
   ```
4. **R2 CORS 設定**（直接アップロードを使う場合）: 第 6 節参照
5. **Worker secrets 投入**:
   ```bash
   wrangler secret bulk secrets.json
   ```
6. **D1 migration の初回適用**:
   ```bash
   wrangler d1 migrations apply <db-name> --remote
   ```
7. **手動 deploy で疎通確認**:
   ```bash
   wrangler deploy
   curl https://<worker-url>/
   ```
8. **CI workflow を有効化**: `main` push でデプロイが走ることを 1 度確認

これらが終わってから CI 自動デプロイ運用に入る。**3-5 を CI に組み込んでも良いが、初回だけは手動でやる** ほうがエラー解析が容易。

---

## 9. ハマりどころと対処

### 9.1 deploy が突然失敗する

| 症状 | 主な原因 |
|---|---|
| `Authentication error [code: 10000]` | API token の scope 不足、または期限切れ |
| `Error: A request to the Cloudflare API ... failed.` | account_id 取り違え、または該当リソースが他アカウントにある |
| `Database not found` | `wrangler.jsonc` の `database_id` がプレースホルダのまま、または別アカウントの DB を参照 |
| `Workflow class not found` | Worker entry から Workflow class が export されていない（OpenNext 等のラッパを使う場合は wrapper entry を作る） |

### 9.2 secrets が反映されない

- **`wrangler secret put` した直後の Worker は古い値で動くことがある**: 新しい version が edge に伝搬するまで数秒の遅延
- **vars に書いた値は deploy しないと反映されない**: secrets と違って **コード変更扱い**
- **Worker の各 region でキャッシュタイミングが違う**: smoke test で連続失敗するなら 30 秒ほど待ってから再試行

### 9.3 R2 から CORS エラー

- **`origins` が完全一致していない**: クエリパラメータ・ポート番号・末尾スラッシュも厳密
- **CORS 設定が反映されるまで数分かかる**: 設定直後はブラウザ側のキャッシュも疑う（DevTools で disable cache）

### 9.4 D1 migration の順序問題

- `wrangler d1 migrations apply --remote` は **deploy より先に走らせる**: 新コードが古い schema で動くと壊れる
- マイグレーション失敗時の自動ロールバックは **無い**: 壊れたら手動で SQL を当て直す覚悟をする
- **down migration は drizzle-kit / wrangler どちらも標準提供されない**: schema 後退時の運用を別途定義する必要あり

### 9.5 Worker bundle size の上限

- Free: 3 MiB（圧縮後 1 MiB）
- Paid: 10 MiB（圧縮後 5 MiB）
- 大きな依存（ffmpeg.wasm 等）を入れると簡単に超える。**重い処理は外部サービス（RunPod / Lambda 等）に逃がす** のが Cloudflare スタックの定石

---

## 10. 参考リンク

- [Cloudflare API Tokens](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/)
- [Wrangler Commands Reference](https://developers.cloudflare.com/workers/wrangler/commands/)
- [Wrangler with GitHub Actions](https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/)
- [D1 Migrations](https://developers.cloudflare.com/d1/reference/migrations/)
- [R2 Presigned URLs](https://developers.cloudflare.com/r2/api/s3/presigned-urls/)
- [R2 CORS](https://developers.cloudflare.com/r2/buckets/cors/)
- [Workers Limits](https://developers.cloudflare.com/workers/platform/limits/)
- [Workflows Limits](https://developers.cloudflare.com/workflows/reference/limits/)
