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

### アーキテクチャ

```
USB カメラ → 撮影 → AI Vision で食材検出 → Cookpad 検索 → 献立提案
              │           │                       │
          camera.py   vision/              planner.py
                    (claude / gemini / ai_hat)
```

### クイックスタート

```bash
# インストール (Claude Vision を使う場合)
pip install cookpad[claude]

# 設定ファイルを作成
cp fridge_config.toml.example fridge_config.toml
# エディタで API キーなどを設定
```

### CLI

```bash
# 利用可能なカメラ一覧
cookpad-fridge cameras

# 撮影して食材を検出
cookpad-fridge scan
cookpad-fridge scan --image 冷蔵庫.jpg     # 既存画像を使う

# 撮影 → 検出 → 献立提案 (フルパイプライン)
cookpad-fridge plan
cookpad-fridge plan --image 冷蔵庫.jpg
cookpad-fridge plan --image 冷蔵庫.jpg --json  # JSON 出力

# 設定ファイルを指定
cookpad-fridge --config my_config.toml plan
```

出力例:

```
📅 2025-01-15 の献立
🥬 検出食材: トマト, 鶏肉, たまねぎ, 卵, にんじん

────────────────────────────────────────
🍽  朝食
  【主菜】ふわふわスクランブルエッグ
         調理時間: 10分
  【副菜1】トマトサラダ

────────────────────────────────────────
🍽  昼食
  【主菜】鶏肉とたまねぎの親子丼
         調理時間: 20分
  【副菜1】にんじんしりしり

────────────────────────────────────────
🍽  夕食
  【主菜】チキンのトマト煮込み
         調理時間: 40分
  【副菜1】たまねぎスープ
  【副菜2】にんじんグラッセ
```

### Python API

```python
import asyncio
from cookpad import Cookpad
from cookpad.fridge import (
    FridgeCamera,
    MealPlanner,
    create_backend,
    load_config,
)

async def main():
    config = load_config("fridge_config.toml")

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
        planner = MealPlanner(cookpad=client)
        plan = await planner.plan_daily(ingredients)
        print(plan.display())

asyncio.run(main())
```

### 設定ファイル

`fridge_config.toml` で動作をカスタマイズできる。

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

[cookpad]
country = "JP"
language = "ja"
```

API キーは環境変数でも渡せる:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export GEMINI_API_KEY="AI..."
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

### モジュール構成

```
cookpad/fridge/
├── __init__.py      # 公開 API exports
├── camera.py        # FridgeCamera, CameraCapture
├── config.py        # FridgeConfig, load_config
├── planner.py       # MealPlanner, DailyMealPlan, Meal
├── cli.py           # cookpad-fridge コマンド
└── vision/
    ├── __init__.py  # VisionBackend (ABC), DetectedIngredient, create_backend
    ├── claude.py    # Claude Vision バックエンド
    ├── gemini.py    # Gemini Vision バックエンド
    └── ai_hat.py    # Raspberry Pi AI HAT バックエンド
```

## ライセンス

MIT
