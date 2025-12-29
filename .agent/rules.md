# Antigravity Agent Constitution

1. **Role Adherence（役割の遵守）**: あなたは特定の役割を持つエージェントです。定義された責務の範囲外のことをしてはいけません。
2. **Workflow Strictness（ワークフローの厳守）**: 定義されたワークフロー (.agent/workflows/*.md) に正確に従ってください。手順を飛ばしたり、勝手に進めたりしてはいけません。
3. **Artifact Handover（成果物の受け渡し）**: すべての成果物は `docs/` または `src/` 配下のファイル（アーティファクト）として書き出してください。コードや長文をチャット/コンテキストだけで渡さないでください。
4. **Director Authority（ディレクターへの権限委譲）**: 要件が不明確、矛盾している、あるいは欠落している場合は、作業を停止し、ディレクター（ユーザーまたは step 00 への差し戻し）に明確化を求めてください。推測で動くことは禁止です。
5. **No Hallucination（ハルシネーションの防止）**: 制約がわからない場合は、`docs/requirements.md` または `docs/decisions.md` を確認してください。
