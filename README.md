# cookpad-py

Cookpad の非公式 Python クライアント。
iPhone 版アプリの API を解析して作った。

Support: [discord.gg/evex](https://discord.gg/evex)

## インストール

```bash
# 基本パッケージ (API クライアントのみ)
pip install cookpad

# 冷蔵庫スマート献立 (Vision バックエンドを選択)
pip install cookpad[claude]    # Claude Vision
pip install cookpad[gemini]    # Gemini Vision
pip install cookpad[ai-hat]    # Raspberry Pi AI HAT (オフライン)

# オプション機能
pip install cookpad[pdf]       # PDF 献立表出力
pip install cookpad[gdrive]    # Google Drive アップロード
pip install cookpad[iaeon]     # iAEON レシート連携 + スケジューラー
pip install cookpad[scheduler] # スケジューラーのみ
pip install cookpad[bypass-otp] # OTP 自動取得

# 全部入り
pip install cookpad[full]
```

## 使い方

一部の引数とかは、認証済みのtokenじゃないと動かないので注意

```python
import asyncio
from cookpad import Cookpad

async def main():
    async with Cookpad() as client:
        # レシピ検索
        results = await client.search_recipes("カレー")
        for recipe in results.recipes:
            print(f"{recipe.title} (つくれぽ: {recipe.cooksnaps_count})")

        # レシピ詳細
        recipe = await client.get_recipe(25410768)
        print(recipe.title)
        for step in recipe.steps:
            print(f"  - {step.description}")

asyncio.run(main())
```

## API

### `Cookpad(*, token, country, language, ...)`

クライアント作成。引数は全部オプショナル。デフォルトで anonymous token 使うからそのまま動いたり動いたりするかもしれないし、動く。

```python
# デフォルト (日本語・匿名)
client = Cookpad()

# カスタム
client = Cookpad(
    # 基本的には要りません
    # token="your_token",
    country="JP",
    language="ja",
    user_agent="custom-ua/1.0",
)
```

### `search_recipes(query, *, page, per_page, order, ...)`

レシピ検索。`SearchResponse` を返す。

```python
results = await client.search_recipes(
    "鶏むね肉",
    order="popular",              # "recent" | "popular" | "date"
    must_have_cooksnaps=True,     # つくれぽありのみ
    minimum_cooksnaps=10,         # つくれぽ10件以上
    included_ingredients="卵",    # 含む材料
    excluded_ingredients="牛乳",  # 除外する材料
    page=1,
    per_page=30,
)

print(f"全 {results.total_count} 件")
for recipe in results.recipes:
    print(f"  {recipe.title}")

# 次のページがあるか
if results.next_page:
    page2 = await client.search_recipes("鶏むね肉", page=results.next_page)
```

### `get_recipe(recipe_id)`

レシピ詳細を取得。`Recipe` を返す。

```python
recipe = await client.get_recipe(25410768)
print(recipe.title)
print(recipe.story)
print(recipe.advice)
print(f"材料 ({recipe.serving}):")
for ing in recipe.ingredients:
    print(f"  {ing.name}: {ing.quantity}")
print("手順:")
for step in recipe.steps:
    print(f"  {step.description}")
```

### `get_similar_recipes(recipe_id, *, page, per_page)`

似てるレシピ一覧。

```python
similar = await client.get_similar_recipes(25410768)
for recipe in similar:
    print(recipe.title)
```

### `get_comments(recipe_id, *, limit, after, label)`

つくれぽ・コメント取得。

```python
comments = await client.get_comments(18510866, limit=10)
for comment in comments.comments:
    print(f"{comment.user.name}: {comment.body}")

# ページネーション (カーソルベース)
if comments.next_cursor:
    more = await client.get_comments(18510866, after=comments.next_cursor)
```

### `search_users(query, *, page, per_page)`

ユーザー検索。

```python
users = await client.search_users("test")
for user in users.users:
    print(f"{user.name} (レシピ数: {user.recipe_count})")
```

### `search_keywords(query)`

検索サジェスト。

```python
suggestions = await client.search_keywords("カレ")
```

### `get_search_history(local_history)`

検索履歴・トレンドキーワード。

```python
history = await client.get_search_history()
```

## 型

レスポンスは全部 dataclass でパース済み。IDE の補完が効く。

- `Recipe` - レシピ (id, title, story, serving, ingredients, steps, ...)
- `Ingredient` - 材料 (name, quantity)
- `Step` - 手順 (description, image_url)
- `User` - ユーザー (id, name, recipe_count, ...)
- `Comment` - コメント/つくれぽ (body, user, image_url, ...)
- `Image` - 画像 (url, filename, alt_text)
- `SearchResponse` - 検索結果 (recipes, total_count, next_page, raw)
- `CommentsResponse` - コメント一覧 (comments, next_cursor)
- `UsersResponse` - ユーザー一覧 (users, total_count, next_page)

`SearchResponse.raw` で API の生レスポンス (dict) にもアクセスできる。

## 例外

```python
from cookpad import CookpadError, AuthenticationError, NotFoundError, RateLimitError, APIError

try:
    recipe = await client.get_recipe(99999999)
except NotFoundError:
    print("レシピが見つからない")
except RateLimitError:
    print("レート制限")
except CookpadError as e:
    print(f"なんかエラー: {e}")
```

---

## 冷蔵庫スマート献立 (`cookpad.fridge`)

冷蔵庫に USB カメラを設置し、AI 画像認識で食材を検出して 1 日 3 食の献立を自動提案する。
各レシピの材料・手順を取得し、冷蔵庫にある食材と要購入食材を判別。PDF 出力・印刷・Google Drive アップロードにも対応。

**iAEON 連携**により、スーパーのレシート情報から食材を自動登録し、**栄養バランスを考慮した献立**を自動生成することもできる。

### アーキテクチャ

```
入力ソース                        処理パイプライン                    出力
──────────                        ────────────                    ────

USB カメラ → 撮影 → AI Vision     ┐
             camera.py  vision/   │
                                  ├→ 食材リスト → Cookpad検索 → 献立表 → PDF/印刷/Drive
iAEON レシート → 食品抽出         │   planner.py                 │
             iaeon/               ┘                               │
                                                           栄養バランス計算
                                                           nutrition/
                                                                  │
                                                        ┌─────────┼─────────┐
                                                        ↓         ↓         ↓
                                                     pdf.py   printer.py  gdrive.py
                                                    (PDF生成)  (lpr印刷)  (Drive保存)

データ永続化: db/ (SQLite)
  - 食品在庫テーブル (food_inventory)
  - 栄養キャッシュ (nutrition_cache)
  - 献立履歴 (meal_plan_history)

スケジューラー: scheduler.py (APScheduler cron)
  - レシート定期取得
  - 献立定期生成
  - 期限切れチェック
```

### クイックスタート

```bash
# インストール (Claude Vision + PDF 出力を使う場合)
pip install cookpad[claude,pdf]

# 設定ファイルを作成
cp fridge_config.toml.example fridge_config.toml
# エディタで API キーなどを設定
```

### CLI コマンド一覧

#### カメラベースのフロー (従来)

```bash
# 利用可能なカメラ一覧
cookpad-fridge cameras

# 利用可能なプリンタ一覧
cookpad-fridge printers

# 撮影して食材を検出
cookpad-fridge scan
cookpad-fridge scan --image 冷蔵庫.jpg     # 既存画像を使う

# 撮影 → 検出 → 献立提案 (フルパイプライン)
cookpad-fridge plan
cookpad-fridge plan --image 冷蔵庫.jpg

# 出力オプション
cookpad-fridge plan --json                        # JSON 出力
cookpad-fridge plan --pdf 献立.pdf                # PDF ファイルに保存
cookpad-fridge plan --print                       # デフォルトプリンタで印刷
cookpad-fridge plan --printer "Brother_HL"        # 指定プリンタで印刷
cookpad-fridge plan --drive                       # Google Drive にアップロード
cookpad-fridge plan --drive --drive-folder ID     # 指定フォルダにアップロード

# 組み合わせ可能
cookpad-fridge plan --image 冷蔵庫.jpg --pdf 献立.pdf --print --drive

# 設定ファイルを指定
cookpad-fridge --config my_config.toml plan
```

#### iAEON 連携フロー (新機能)

```bash
# iAEON ログイン (初回セットアップ)
cookpad-fridge iaeon-login

# レシート手動取得 → 食品を DB に登録
cookpad-fridge iaeon-fetch              # 過去7日分
cookpad-fridge iaeon-fetch --days 14    # 過去14日分

# 食品在庫を表示
cookpad-fridge inventory                # 全在庫
cookpad-fridge inventory --expiring     # 期限切れ間近のみ
cookpad-fridge inventory --json         # JSON 出力
```

#### 栄養バランス献立 (新機能)

```bash
# DB の在庫から栄養バランスを考慮した献立を生成
cookpad-fridge nutrition-plan
cookpad-fridge nutrition-plan --json                # JSON 出力
cookpad-fridge nutrition-plan --pdf 献立.pdf        # PDF 保存
cookpad-fridge nutrition-plan --pdf 献立.pdf --drive  # PDF + Drive

# 食品栄養情報を検索 (MEXT 日本食品標準成分表)
cookpad-fridge nutrition-lookup トマト
cookpad-fridge nutrition-lookup 鶏もも肉
```

#### スケジューラー (新機能)

```bash
# スケジューラーを起動 (cron で定期実行)
cookpad-fridge schedule start

# ジョブ登録状況を確認
cookpad-fridge schedule status
```

### 出力例

#### 通常の献立表

```
📅 2025-01-15 の献立
🥬 検出食材: トマト, 鶏肉, たまねぎ, 卵, にんじん

──────────────────────────────────────────────────
🍽  朝食

  【主菜】ふわふわスクランブルエッグ
         調理時間: 10分
         分量: 2人分

    食材名     分量       保存場所 状態
    ────────────────────────────────────────────
    卵         3個        ドアポケット ✓ 冷蔵庫にあり
    牛乳       大さじ2    チルド室 要購入
    バター     10g        チルド室 要購入
    塩         少々       ドアポケット 要購入

    手順:
      1. 卵をボウルに割り入れ、牛乳と塩を加えて混ぜる
      2. フライパンにバターを溶かし、中火で卵液を流し入れる
      3. 大きくかき混ぜ、半熟で火を止める

  【副菜1】トマトサラダ

──────────────────────────────────────────────────
🛒 買い物リスト

    食材名     分量       保存場所
    ──────────────────────────────
    牛乳       大さじ2    チルド室
    バター     10g        チルド室
```

#### 栄養バランス付き献立表 (`nutrition-plan`)

```
📅 2025-01-15 の献立
🥬 検出食材: トマト, 鶏もも肉, 卵, たまねぎ

  ... (献立詳細) ...

──────────────────────────────────────────────────
栄養バランス

  栄養素     摂取量     目標       達成率
  ────────────────────────────────────────────
  エネルギー 1856kcal   2000kcal   93%
  たんぱく質 72.3g      75.0g      96%
  脂質       48.1g      55.6g      87%
  炭水化物   268.5g     300.0g     90%
  食物繊維   18.2g      21.0g      87%
  食塩相当量 6.8g       7.5g以下   91%

  PFC比率: P16% / F23% / C58%
  バランススコア: 0.92
```

### iAEON 連携

iAEON アプリの購入履歴からレシート情報を取得し、購入した食品を自動で在庫管理する。

#### セットアップ

1. `pip install cookpad[iaeon]`
2. 設定ファイルに iAEON の認証情報を追加:

```toml
[iaeon]
enabled = true
phone = "090-1234-5678"     # または環境変数 IAEON_PHONE
password = "your_password"  # または環境変数 IAEON_PASSWORD
otp_method = "manual"       # "manual" (手動入力) | "bypass" (自動)
```

3. 初回ログイン: `cookpad-fridge iaeon-login`

#### フロー

```
iAEON レシート取得 → 商品名正規化 → 食品フィルタ → 期限推定 → SQLite 保存
                     (TV/BP除去)    (日用品除外)    (カテゴリ別)
```

商品名正規化:
- AEON ブランド接頭辞 (TV, BP, トップバリュ) を除去
- 数量/重量ラベル (300g, 3個入) を除去
- 産地ラベル (北海道産, 国産) を除去

賞味期限推定:
| カテゴリ | 推定日数 |
|---|---|
| 肉・魚 | +3日 |
| 野菜・果物 | +7日 |
| 乳製品 | +10日 |
| 卵 | +14日 |
| 穀物 | +30日 |
| 調味料 | +180日 |

### 栄養バランス計算

日本食品標準成分表 (MEXT 2020年版八訂) をベースに、レシピの栄養価を計算する。

#### 機能

- **レシピ栄養計算**: 材料名を MEXT データベースと照合し、エネルギー・PFC・食物繊維・食塩相当量等を算出
- **PFC バランススコア**: たんぱく質(P)・脂質(F)・炭水化物(C) の比率が目標にどれだけ近いかを 0.0〜1.0 で評価
- **日本語調理単位変換**: 大さじ/小さじ/カップ/合/個/本/枚 などをグラムに変換
- **食品別重量テーブル**: 卵1個=60g, トマト1個=150g, 鶏もも肉1枚=250g など

#### 栄養目標のデフォルト値

| 項目 | デフォルト | 根拠 |
|---|---|---|
| エネルギー | 2000 kcal | 日本人の食事摂取基準 |
| たんぱく質 | 15% | 推奨 PFC 比率 |
| 脂質 | 25% | 推奨 PFC 比率 |
| 炭水化物 | 60% | 推奨 PFC 比率 |
| 食塩相当量 | 7.5g 以下 | 厚生労働省目標値 |
| 食物繊維 | 21g 以上 | 厚生労働省目標値 |

設定ファイルでカスタマイズ可能:

```toml
[nutrition]
enabled = true
energy_target = 1800     # 目標エネルギー (kcal)
protein_pct = 20         # たんぱく質比率 (%)
fat_pct = 20             # 脂質比率 (%)
carb_pct = 60            # 炭水化物比率 (%)
salt_max = 6.0           # 食塩上限 (g)
fiber_min = 25           # 食物繊維下限 (g)
prioritize_expiring = true
```

### スケジューラー

APScheduler で cron ベースの定期実行を行う。

| ジョブ | デフォルトスケジュール | 処理内容 |
|---|---|---|
| レシート取得 | 毎日 8:00 | iAEON → レシート取得 → 食品 DB 登録 |
| 献立生成 | 毎日 6:00 | 在庫 → 栄養バランス献立 → PDF → Google Drive |
| 期限切れチェック | 毎日 0:00 | 期限切れ食品のステータス更新 |

```toml
[iaeon]
fetch_schedule = "0 8 * * *"   # cron式
plan_schedule = "0 6 * * *"
```

### PDF 出力

`--pdf` で献立表を PDF ファイルに保存できる。A4 レイアウトで材料テーブル・手順・買い物リスト付き。
`nutrition-plan` の場合は栄養バランスサマリー (PFC テーブル + スコア) も付く。

```bash
pip install cookpad[pdf]  # reportlab が必要

cookpad-fridge plan --pdf 献立.pdf
cookpad-fridge nutrition-plan --pdf 献立.pdf
```

日本語フォント (`fonts-noto-cjk` など) が必要:

```bash
# Ubuntu/Debian
sudo apt install fonts-noto-cjk

# Fedora/RHEL
sudo dnf install google-noto-sans-cjk-ttc-fonts
```

### 印刷

`--print` / `--printer` で PDF を自動印刷。CUPS の `lpr` コマンドを使用。

```bash
# デフォルトプリンタで印刷
cookpad-fridge plan --print

# プリンタを指定
cookpad-fridge plan --printer "Brother_HL"

# プリンタ一覧を確認
cookpad-fridge printers
```

### Google Drive アップロード

`--drive` で献立 PDF を Google Drive に自動保存。

```bash
pip install cookpad[gdrive]  # google-auth-oauthlib, google-api-python-client が必要

cookpad-fridge plan --drive
cookpad-fridge plan --drive --drive-folder "フォルダID"
```

**初回セットアップ:**

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
2. Google Drive API を有効化
3. OAuth 2.0 クライアント ID を作成 (デスクトップアプリ)
4. クレデンシャル JSON を `~/.config/cookpad/gdrive_credentials.json` に保存
5. 初回実行時にブラウザで認証 (トークンは自動保存)

### Python API

```python
import asyncio
from cookpad import Cookpad
from cookpad.fridge import (
    FridgeCamera,
    MealPlanner,
    NutritionAwareMealPlanner,
    create_backend,
    load_config,
)

async def main():
    config = load_config("fridge_config.toml")

    # === カメラベースのフロー ===

    # 1. 撮影
    camera = FridgeCamera(
        camera_indices=config.camera.indices,
        save_dir=config.camera.save_dir,
    )
    captures = camera.capture_all()
    image_paths = [c.image_path for c in captures]

    # 2. 食材検出
    backend = create_backend(config)
    ingredients = await backend.detect_ingredients(image_paths)

    for ing in ingredients:
        print(f"{ing.name} ({ing.confidence:.0%}) [{ing.category}]")

    # 3. 献立提案
    async with Cookpad(country="JP", language="ja") as client:
        planner = MealPlanner(
            cookpad=client,
            storage_locations=config.planner.storage_locations,
        )
        plan = await planner.plan_daily(ingredients)
        print(plan.display())

        # 買い物リスト
        for item in plan.shopping_list():
            print(f"  要購入: {item.name} {item.quantity} ({item.storage_location})")

    # 4. PDF 出力 (オプション)
    from cookpad.fridge.pdf import generate_pdf
    generate_pdf(plan, "献立.pdf")

    # === iAEON + 栄養バランスのフロー ===

    # 1. iAEON レシートから在庫取得
    from cookpad.fridge.db import InventoryDB
    db = InventoryDB(config.database.path)
    ingredients = db.get_inventory_as_ingredients()

    # 2. 栄養バランス献立生成
    from cookpad.fridge.nutrition import NutritionTargets
    targets = NutritionTargets(energy_kcal=2000)

    async with Cookpad(country="JP", language="ja") as client:
        planner = NutritionAwareMealPlanner(
            cookpad=client,
            nutrition_targets=targets,
        )
        plan = await planner.plan_daily_balanced(ingredients=ingredients)
        print(plan.display())  # 栄養バランスセクション付き

    # 3. 栄養付き PDF
    generate_pdf(plan, "献立.pdf", daily_nutrition=plan.daily_nutrition)

    # === 栄養情報の直接検索 ===

    from cookpad.fridge.nutrition import MEXTDatabase
    mext = MEXTDatabase.instance()
    info = mext.lookup_by_name("トマト")
    if info:
        print(f"{info.name}: {info.energy_kcal}kcal, P{info.protein}g, F{info.fat}g, C{info.carbohydrate}g")

asyncio.run(main())
```

### Vision バックエンド

| バックエンド | SDK | 特徴 |
|---|---|---|
| `claude` | `anthropic` | 高精度。日本の食材に強い |
| `gemini` | `google-generativeai` | 高速。無料枠あり |
| `ai_hat` | `hailort` | Raspberry Pi でオフライン動作。YOLO ベース |

自作バックエンドも作れる:

```python
from cookpad.fridge import VisionBackend, DetectedIngredient

class MyBackend(VisionBackend):
    async def detect_ingredients(self, image_paths: list[str]) -> list[DetectedIngredient]:
        # 独自の検出ロジック
        return [DetectedIngredient(name="トマト", confidence=0.9, category="野菜")]
```

### 設定ファイル

`fridge_config.toml` で動作をカスタマイズできる。全セクションはオプショナルで、未指定の場合はデフォルト値が使われる。

```toml
[camera]
indices = [0, 1]           # USB カメラのインデックス
save_dir = "/tmp/fridge"

[vision]
backend = "claude"         # "claude" | "gemini" | "ai_hat"
min_confidence = 0.5       # 最低信頼度 (これ未満の食材は無視)

[vision.claude]
api_key = ""               # 空なら ANTHROPIC_API_KEY 環境変数
model = "claude-sonnet-4-5-20250929"

[vision.gemini]
api_key = ""               # 空なら GEMINI_API_KEY 環境変数
model = "gemini-2.0-flash"

[vision.ai_hat]
model_path = "/usr/share/hailo-models/yolov8s.hef"

[planner]
meals_per_day = 3
recipes_per_meal = 3       # 主菜1 + 副菜2

# カテゴリ別の保管場所をカスタマイズ
# [planner.storage_locations]
# 野菜 = "野菜室"
# 肉 = "チルド室"
# 卵 = "ドアポケット"

[cookpad]
country = "JP"
language = "ja"

[printer]
enabled = false            # true で plan 時に自動印刷
printer_name = ""          # 空ならデフォルトプリンタ

[gdrive]
enabled = false            # true で plan 時に自動アップロード
credentials_path = "~/.config/cookpad/gdrive_credentials.json"
token_path = "~/.config/cookpad/gdrive_token.json"
folder_id = ""             # 空ならマイドライブ直下

[iaeon]
enabled = false            # true で iAEON 連携を有効化
phone = ""                 # 空なら IAEON_PHONE 環境変数
password = ""              # 空なら IAEON_PASSWORD 環境変数
otp_method = "manual"      # "manual" | "bypass"
fetch_schedule = "0 8 * * *"   # レシート取得 cron 式
plan_schedule = "0 6 * * *"    # 献立生成 cron 式
receipt_days = 7

[database]
path = "~/.config/cookpad/inventory.db"

[nutrition]
enabled = true
energy_target = 2000       # 目標エネルギー (kcal)
protein_pct = 15           # たんぱく質比率 (%)
fat_pct = 25               # 脂質比率 (%)
carb_pct = 60              # 炭水化物比率 (%)
salt_max = 7.5             # 食塩上限 (g)
fiber_min = 21             # 食物繊維下限 (g)
prioritize_expiring = true # 期限切れ間近の食品を優先
```

API キーは環境変数でも渡せる:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export GEMINI_API_KEY="AI..."
export IAEON_PHONE="090-1234-5678"
export IAEON_PASSWORD="your_password"
```

### データベース

SQLite (`~/.config/cookpad/inventory.db`) に以下のテーブルを自動作成:

| テーブル | 用途 |
|---|---|
| `food_inventory` | iAEON から取得した食品在庫 (名前, カテゴリ, 数量, 期限, 価格, ステータス) |
| `nutrition_cache` | MEXT 栄養情報の検索キャッシュ |
| `meal_plan_history` | 生成済み献立の履歴 (日付, 栄養情報, PDF パス, Drive ID) |

### モジュール構成

```
cookpad/
├── __init__.py          # Cookpad API クライアント公開 API
├── client.py            # Cookpad 非同期 HTTP クライアント
├── types.py             # Recipe, Ingredient, Step 等のデータ型
├── constants.py         # API ベース URL, デフォルトトークン
├── exceptions.py        # CookpadError, NotFoundError 等
└── fridge/              # 冷蔵庫スマート献立モジュール
    ├── __init__.py      # 公開 API exports
    ├── config.py        # FridgeConfig, IAEONConfig, NutritionConfig, load_config
    ├── camera.py        # FridgeCamera, CameraCapture
    ├── planner.py       # MealPlanner, NutritionAwareMealPlanner, DailyMealPlan
    ├── pdf.py           # generate_pdf (ReportLab PDF 生成, 栄養セクション対応)
    ├── printer.py       # Printer (lpr 印刷)
    ├── gdrive.py        # GoogleDriveUploader (Google Drive OAuth 2.0)
    ├── scheduler.py     # MealPlanScheduler (APScheduler cron ジョブ)
    ├── cli.py           # cookpad-fridge コマンド (12 サブコマンド)
    ├── vision/          # AI 画像認識バックエンド
    │   ├── __init__.py  # VisionBackend (ABC), DetectedIngredient, create_backend
    │   ├── claude.py    # Claude Vision バックエンド
    │   ├── gemini.py    # Gemini Vision バックエンド
    │   └── ai_hat.py    # Raspberry Pi AI HAT バックエンド
    ├── iaeon/           # iAEON レシート連携
    │   ├── __init__.py
    │   ├── models.py    # ReceiptEntry, FoodItem データクラス
    │   ├── otp.py       # OTPHandler (Manual / Bypass)
    │   ├── auth.py      # IAEONAuthenticator (ログイン・OTP 処理)
    │   └── receipts.py  # ReceiptFetcher (レシート取得・商品名正規化・期限推定)
    ├── nutrition/       # 栄養バランス計算
    │   ├── __init__.py
    │   ├── mext_data.py # MEXTDatabase (日本食品標準成分表, シングルトン)
    │   ├── units.py     # parse_quantity, to_grams (日本語調理単位変換)
    │   ├── calculator.py # NutritionCalculator, NutritionTargets, DailyNutrition
    │   └── data/
    │       └── mext_2020_v8.json  # 成分表バンドルデータ (60+ 食品)
    └── db/              # SQLite データベース
        ├── __init__.py
        ├── schema.py    # DDL 定義・スキーマ管理
        ├── inventory.py # InventoryDB (食品在庫 CRUD)
        ├── nutrition_cache.py  # NutritionCacheDB
        └── meal_history.py     # MealHistoryDB (献立履歴)
```

### テスト

```bash
pip install pytest pytest-asyncio

# 全テスト実行
pytest tests/ -v

# モジュール別
pytest tests/test_db_schema.py tests/test_db_inventory.py -v     # DB
pytest tests/test_nutrition_units.py tests/test_nutrition_mext.py tests/test_nutrition_calculator.py -v  # 栄養
pytest tests/test_iaeon_receipts.py tests/test_iaeon_auth.py -v  # iAEON
pytest tests/test_planner_nutrition.py -v                        # 栄養プランナー
pytest tests/test_config_iaeon.py -v                             # 設定
pytest tests/test_scheduler.py -v                                # スケジューラー
```

## ライセンス

MIT
