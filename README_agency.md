# Agency Structure Project

このプロジェクトは、Antigravity向けのマルチエージェント・ワークフローを実装したものです。
ファイルベースの構造を使用して、AIエージェントの役割、責任、およびワークフローを定義しています。

## ディレクトリ構造

- `.agent/`: エージェントの設定とワークフロー。
  - `rules.md`: 憲法（変更不可のルール）。
  - `agents/`: 役割定義（Director, Researcher, Coder, QA）。
  - `workflows/`: ステップバイステップの手順書。
- `docs/`: ドキュメントと成果物（関心の分離を適用）。
  - `requirements.md`: *何* を作るかを定義。
  - `decisions.md`: *どのように*、*なぜ* そうするのかを定義。
  - `research/`: Researcherによる一次調査データ。
- `src/`: プロダクションコード（Coderのみが触れる）。
- `tests/`: テストコード。

## 役割 (Roles)

- **Director**: プロジェクトマネージャー兼プランナー。
- **Researcher**: 情報収集係。
- **Coder**: 実装のスペシャリスト。
- **QA**: 品質保証の監査官。

## 使い方

Directorのワークフローを実行して開始します：
`@Director /run_workflow .agent/workflows/00_direct_plan.md`
（または単にAntigravityに「プロジェクトの計画を開始して」と依頼してください）

## 高度なテクニック：チーム編成 (Team Optimization)

プロジェクトの要件が決まったら、**エージェント自身に役割定義を書き換えさせて、チームを最適化する**ことができます。

例：
> 「@Director 要件定義書 (docs/requirements.md) に基づいて、Coderの専門性を最適化してください。今回はReactとTypeScriptを使うので、それらのエキスパートとして振る舞うよう `.agent/agents/coder.md` を書き換えてください」

これにより、一般的なコーダーから「そのプロジェクト専用のスペシャリスト」へと進化させることができます。
