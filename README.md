# Kindle Marketing AI

**独立したAmazon広告のCSV分析アプリ**です。X Reply Assistantとは別のGitHubリポジトリ・別のStreamlitアプリで運用します。XのAPIキー、Supabase、Xアプリの費用設定は使用しません。

## 現在の機能（v0.1）

- Amazonスポンサープロダクト広告の日本語・英語CSVを複数読み込み、キャンペーン・検索語句・ターゲティングの実績を集計
- 広告費、クリック、表示、注文、広告売上、CTR、CPC、CVR、ACOSと、入力した印税に基づく参考収支
- 売上反映の遅れを考慮した保守的な改善候補（検索語句除外/入札見直し等）と承認・保留・却下
- AI分析とX告知文の生成は、Claude APIキーと毎回の同意がある場合のみ利用
- 施策CSV、分析結果JSONをダウンロード可能。サンプルデータで操作を試せます

**重要：現在の版は広告アカウントを操作しません。「承認」しても広告の予算・入札・キーワードは変更されません。** Amazon Ads APIの利用資格・認可を確認してから、自動同期・自動変更を追加検討します。ブラウザ自動ログインやスクレイピングは行いません。

## iPhoneでStreamlitアプリに公開する手順

1. [share.streamlit.io](https://share.streamlit.io/) をSafariで開き、GitHubでログイン
2. **Create app → Deploy a public app from GitHub** を選択
3. Repository: `naoyukitakahashi1031-sketch/kindle-marketing-ai` 、Branch: `main`、Main file path: `app.py`
4. **Advanced settings / Secrets** に、秘密の長いパスワードを指定：
   ```toml
   APP_PASSWORD = "ここを推測されにくい固有のパスワードに変更"
   ```
5. Deploy。発行された新しいURLはX Reply Assistantとは異なります。Safariからホーム画面に追加できます。

Private repositoryを使用しています。Streamlit側に当該リポジトリの参照権限が必要です。接続できないときは、StreamlitのGitHub権限を確認してください。APIキーやパスワードはGitHubファイルには絶対記入しないでください。**APP_PASSWORDが未設定ならアプリはロックされます。**

### Claude AI（任意・有料）

Anthropic ConsoleでAPIキーを取得してStreamlit Secretsに `ANTHROPIC_API_KEY` を追加します。API費用はAnthropic側で上限を管理。既存のXアプリとは別のSecretsで設定し、共有しません。

### CSVの扱い

Amazon広告のキャンペーンCSVが最も確実な全体集計元です。検索語句CSV等は同じ広告クリックを別の粒度で示すため、全部を足すと二重計上です。このアプリは全体集計に1種類だけ採用します。同じ種類のCSVを期間重複して取り込まないでください。キャンペーン選択により他書籍の広告を除外できます。

レポートの日付はCSV内部を絞り込む機能ではありません。Amazon広告側で日付を指定してダウンロードしてください。KDP総販売数を広告注文と単純に足さないでください。KU収益等は概算損益の対象外です。

### セキュリティ・保存

管理画面はパスワード必須。CSVはセッション中のみ使い永続DBには保存しません。外部AIにはボタンを押して同意した場合のみ、集計値と候補内容が送信されます。パスワードによる簡易保護は企業向けの認証システムではありません。

## 将来の拡張

Amazon Ads APIの認可を受けた後、OAuth、日次レポート取得、書籍別管理、差分検出、変更プレビュー、予算上限と承認記録を実装します。API許可前は自動変更機能を実装しません。

## 開発

```bash
pip install -r requirements-dev.txt
pytest -q
streamlit run app.py
```
