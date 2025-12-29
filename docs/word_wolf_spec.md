# Word Wolf（ワードウルフ）- 追加ゲームモード仕様書

> **Version**: 2.0 (Integrated Mode)
> **Last Updated**: 2025-12-28
> **Parent Project**: Sympathy Game

---

## 1. 統合方針 (Integration Strategy)

### 1.1 コンセプト
既存の「Sympathy」プラットフォーム上で動作する**第2のゲームモード**として実装します。
ユーザーは同じURL、同じルーム、同じアバターで、シームレスに「Sympathy」と「Word Wolf」を切り替えて遊ぶことができます。

### 1.2 共有リソース (Shared Assets)
以下の機能はSympathyの既存実装を流用します。
- **Lobby System**: ルーム作成、QRコード参加、ユーザー一覧表示。
- **Connection**: WebSocket接続、切断ハンドリング。
- **Design System**: Glassmorphism UI、共通コンポーネント（ボタン、アバター）。
- **User Identity**: ニックネーム、アバター設定。

---

## 2. ゲームルール (Game Rules) -> *No Change*
基本ルールは [Version 1.0](word_wolf_spec.md) に準拠します。
ただし、**3〜4人でのプレイ体験**を最適化するため、デフォルト設定を以下のようにします。
- 議論時間: 3分
- ウルフ: 1人

---

## 3. 画面仕様 (Screen Specifications)

### 3.1 Mode Select (New Screen)
ホストのロビー画面に「ゲーム選択」を追加します。

```
+---------------------------------------+
|  Game Select                          |
|                                       |
|  [ 💖 Sympathy ]  [ 🐺 Word Wolf ]    |
|   共感パーティ       正体隠匿系       |
|                                       |
|  Current Mode: Sympathy               |
+---------------------------------------+
```

### 3.2 Host Screen (Word Wolf Mode)
基本レイアウトはSympathyと共通化します。
- **Header**: タイトル、残り時間。
- **Main Area**: 
    - 議論中: 全員のアバターとステータス（発言中など）。
    - 投票中: 投票状況グリッド。
    - 結果: Sympathyの「正解発表」UIを流用し、ウルフを強調表示。

### 3.3 Player Screen (Word Wolf Mode)
- **Top Bar**: 自分の役割（市民/ウルフ）をアイコンで常時表示（タップで詳細確認）。
- **Main**: 
    - 議論中: 「お題」を大きく表示（覗き見防止フィルター付き）。
    - 投票中: プレイヤーリストからタップして投票。

---

## 4. データモデル拡張 (Data Model Extension)

### 4.1 Game State
`GameState` に `mode` プロパティを追加し、モードごとの処理を分岐させます。

```json
{
  "room_id": "ABCD",
  "status": "playing",
  "mode": "word_wolf", // OR "sympathy"
  "game_data": {
    // Mode-specific data
    "wolf_ids": ["player_123"],
    "topics": {"majority": "Apple", "minority": "Orange"}
  }
}
```

### 4.2 API / WebSocket
`/start_game` エンドポイントに `mode` パラメータを追加します。

---

## 5. 開発ロードマップ (Integration Roadmap)

1.  **Refactor**: ホスト側の状態管理を「ロビー」と「ゲーム進行」に分離。
2.  **Mode Switch**: ロビー画面にゲームモード選択UIを追加。
3.  **Wolf Logic**: Word Wolf用のサーバーサイドロジック（お題配布、投票集計）を実装。
4.  **UI Adapt**: 既存コンポーネント（Timer, PlayerGrid）をWord Wolf用にスタイル調整。
