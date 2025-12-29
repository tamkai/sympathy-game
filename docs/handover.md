# Handover Guide: Sympathy Game (Biz -> Dev)

ビジネス・マーケティングチーム（Biz）での検討フェーズが完了しました。
以下のドキュメントと方針を開発チーム（Dev）に引き継ぎます。

## 1. Key Documents (成果物一覧)
開発着手前に必ず以下のドキュメントを確認してください。

| ドキュメント | 内容 | 優先度 |
|---|---|---|
| [**Business Plan**](business_plan.md) | プロダクトの目的、プラットフォーム構想、収益化戦略。 | High |
| [**Word Wolf Spec**](word_wolf_spec.md) | **★新規追加**: Sympathyに追加する第2のゲームモード仕様。 | High |
| [**Concept LP**](campaigns/lp_concept.md) | 世界観を伝えるランディングページの構成案。 | High |
| [**Design System**](design_system.md) | 配色、フォント、Glassmorphismの実装ガイドライン。 | High |

## 2. Key Concepts for Development
開発時に特に意識してほしいポイントです。

### "Platform Architecture" (New!)
*   **Concept**: 1つのURL、1つのWebSocket接続で、複数のゲームモードを切り替えて遊べる設計にしてください。
*   **Scalability**: 将来的に第3、第4のゲームを追加しやすくするために、Game Logicをモジュール化してください。

### "Glassmorphism & Pop"
*   **Visual**: すりガラスのような質感 (`backdrop-filter: blur`) と、鮮やかなグラデーション背景。
*   **Motion**: ふわふわと浮遊するようなアニメーション。

### "Definition of Done" (Biz Side)
Bizサイドとして、MVPに期待する完成定義です。

- [ ] **Mode Select**: ロビー画面で「Sympathy」と「Word Wolf」を選択できること。
- [ ] **Sympathy Mode**: 旧来の仕様通り動作すること。
- [ ] **Word Wolf Mode**: 新仕様書に基づき、議論〜投票〜結果までが動作すること。
- [ ] **Aesthetics**: Design Systemに準拠し、モード間で統一感のあるUXを提供すること。

---
Good luck, Dev Team!
*-- Director & Biz Team*
