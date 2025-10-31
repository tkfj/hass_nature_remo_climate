# Nature Remo Climate (HACS Custom Integration)
最小のサンプル統合。Home Assistant に「空のエアコン」エンティティを1つだけ表示します。機能はありません。

## 手順
1. このリポジトリをGitHubへ公開し、Release(例: v0.0.1)を作成
2. HACS → Integrations → Custom repositories でURLを追加（Category: Integration）
3. HACSからインストール → HA再起動 → 設定→デバイスとサービス→統合を追加→ **Nature Remo Climate**

## 仕様
- エンティティは `climate.nature_remo_climate`（実際のentity_idは環境で異なる）
- 値はすべて `None` / モードは `OFF` 固定
- 操作しても状態は変化しません（雛形用途）
