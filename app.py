"""Kindle Marketing AI - CSV-first, read-only Kindle advertising assistant."""
from __future__ import annotations
import hmac
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd
import streamlit as st

from kma.core import read_csv, summarize, breakdown, proposals, safe_csv

JST = ZoneInfo("Asia/Tokyo")
st.set_page_config(page_title="Kindle Marketing AI", page_icon="📚", layout="wide")
def setting(key, default=""):
    try:
        return st.secrets.get(key, default)
    except (FileNotFoundError, KeyError):
        return default

def gate():
    password = setting("APP_PASSWORD")
    if not password:
        st.error("管理パスワード未設定のためアクセスを停止しました。Streamlit Cloud のSettings→Secretsに APP_PASSWORD を設定してください。")
        return False
    if st.session_state.get("logged_in"):
        return True
    st.title("📚 Kindle Marketing AI")
    st.caption("Amazon広告分析ツール・管理者ログイン")
    with st.form("login"):
        entered = st.text_input("パスワード", type="password")
        if st.form_submit_button("ログイン"):
            if hmac.compare_digest(entered, str(password)):
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("パスワードが違います。")
    return False
if not gate():
    st.stop()

st.title("📚 Kindle Marketing AI")
st.caption("X Reply Assistantとは独立したアプリ｜初期版はCSV分析・変更案の作成のみ。Amazon広告への変更はしません。")
with st.sidebar:
    st.subheader("📖 対象書籍")
    book = st.text_input("書籍名", "YouTube登録者6万人の経験をまとめたKindle本")
    asin = st.text_input("ASIN（任意）")
    price = st.number_input("販売価格（円）", min_value=0, value=99, step=10)
    royalty = st.number_input("1冊あたり実際の印税・概算（円）", min_value=0.0, value=32.0, step=1.0)
    objective = st.selectbox("運用目的", ["認知・ランキング重視（赤字許容）","利益重視","データ収集"])
    spend_cap = st.number_input("広告費の1日平均の監視目安（円）※広告設定ではありません", min_value=0, value=500, step=100)
    kdp_orders = st.number_input("KDP総販売数（手入力・任意）", min_value=0, value=0)
    today = datetime.now(JST).date()
    period_end = st.date_input("レポート期間終了日", value=today, max_value=today)
    period_start = st.date_input("レポート期間開始日", value=today-timedelta(days=13), max_value=today)
    st.caption("日付はレポートの記録用です。CSVの内容を日付でフィルタするものではありません。")
    st.divider()
    uploads = st.file_uploader("Amazon Ads CSVを追加（キャンペーン・検索語句・ターゲティング）", type=["csv","txt"], accept_multiple_files=True)
    sample = st.checkbox("架空のサンプルデータで試す", value=False)
    st.caption("⚠️ Amazon広告の入札、予算、除外キーワードは自動変更されません。")

if period_start>period_end:
    st.error("開始日が終了日より後です。")
    st.stop()

reports = []
for u in uploads or []:
    try:
        reports.append(read_csv(u.getvalue(), u.name))
    except (ValueError, UnicodeError, pd.errors.ParserError) as exc:
        st.error(f"{u.name}：{exc}")
if sample and not uploads:
    for name in ("campaign_sample.csv","search_terms_sample.csv"):
        reports.append(read_csv((Path(__file__).parent/"examples"/name).read_bytes(),name))
    st.warning("🧪 デモ：表示中の数字は架空のデータです。実際の成果ではありません。")
if not reports:
    st.info("まず左のメニューからAmazon広告のCSVをアップロードしてください。画面を試すならサンプルデータを有効にしてください。")
    st.stop()

for r in reports:
    for msg in r.warnings:
        st.caption(f"{r.name}：{msg}")
if len({(r.name,r.kind) for r in reports}) < len(reports):
    st.warning("同名レポートを重複アップロードした可能性があります。期間の重複集計に注意。")
all_campaigns = sorted({str(c) for r in reports for c in r.data.campaign.unique()})
selected = st.multiselect("分析するキャンペーン（他の書籍のものは外す）",all_campaigns,default=all_campaigns)
if not selected:
    st.stop()
kinds = {}
for r in reports:
    kinds.setdefault(r.kind,[]).append(r.data.loc[r.data.campaign.isin(selected)].copy())
kinds = {k:pd.concat(v, ignore_index=True) for k,v in kinds.items()}
primary_kind = next((k for k in ["キャンペーン","ターゲティング","検索語句"] if k in kinds),None)
if primary_kind is None:
    st.stop()
# Do not sum all report levels: they contain the same clicks from different perspectives.
primary = kinds[primary_kind]
summary = summarize(primary,royalty)
days = (period_end-period_start).days+1
daily = summary["spend"]/days
settled = (period_end <= today-timedelta(days=14)) and days>=7
if not settled:
    st.info("直近の広告注文や売上は反映遅延の可能性があります。停止・入札変更は慎重に判断してください。")
if spend_cap and daily > spend_cap:
    st.warning(f"期間平均の広告費 ¥{daily:,.0f}/日 が監視目安 ¥{spend_cap:,.0f}/日 を上回っています。Amazon広告側の設定をご確認ください。")
if primary_kind != "キャンペーン":
    st.warning(f"キャンペーンCSVがないため、全体集計は{primary_kind}データを使用しています。")
st.subheader("📊 広告ダッシュボード")
cols = st.columns(4)
for c,label,value in zip(cols,["広告費","クリック数","広告注文","広告売上"],[f"¥{summary['spend']:,.0f}",f"{summary['clicks']:,.0f}",f"{summary['orders']:,.0f}",f"¥{summary['sales']:,.0f}"]):
    c.metric(label,value)
cols = st.columns(4)
for c,label,value in zip(cols,["CTR","平均CPC","CVR","ACOS"],[f"{summary['ctr']:.2f}%",f"¥{summary['cpc']:.1f}",f"{summary['cvr']:.2f}%",f"{summary['acos']:.1f}%" if summary['acos'] is not None else "算定不可"]):
    c.metric(label,value)
st.caption(f"平均広告費 ¥{daily:,.0f}/日｜KDP総販売数（手入力）{kdp_orders}冊｜データ基準：{primary_kind}")
with st.expander("印税ベースの参考収支"):
    st.metric("広告注文×入力印税－広告費（概算・利益ではありません）",f"¥{summary['indicative_margin']:,.0f}")
    st.write("KU既読ページ収益や広告外売上等を含みません。広告注文とKDP総販売数を合算しないでください。")

actions=[]
for scope, df in kinds.items():
    actions.extend(proposals(df,scope,royalty,settled))
action_frame=pd.DataFrame(actions,columns=["priority","type","campaign","target","recommendation","evidence","decision"])
details, tasks, ai_tab, exports = st.tabs(["📉 詳細分析","🎯 改善アクション","🧠 Claude AI","📄 データ出力"])
with details:
    for scope,df in kinds.items():
        st.markdown(f"#### {scope}別実績")
        by=["campaign"]+(["search_term"] if scope=="検索語句" else ["target"] if scope=="ターゲティング" else [])
        st.dataframe(breakdown(df,by),hide_index=True,use_container_width=True)
with tasks:
    st.caption("「承認」は改善案の採用を意味します。Amazon広告の設定には反映されません。")
    if action_frame.empty:
        st.info("現状の基準では候補がありません。データ不足の可能性もあります。")
        edited=action_frame
    else:
        edited=st.data_editor(action_frame,num_rows="fixed",hide_index=True,use_container_width=True,
            disabled=[c for c in action_frame.columns if c!="decision"],
            column_config={"decision":st.column_config.SelectboxColumn("判断",options=["未判断","承認（手動反映待ち）","保留","却下"],required=True)})
    st.download_button("改善案CSVを保存",safe_csv(edited),file_name="kindle_action_plan.csv",mime="text/csv")
    st.warning("広告アカウントでの設定変更は、ご自身で確認して手動実施してください。")
with ai_tab:
    api_key=str(setting("ANTHROPIC_API_KEY",""))
    model=str(setting("ANTHROPIC_MODEL","claude-sonnet-5-5"))
    if not api_key:
        st.info("Claude未接続。Streamlit SecretsにANTHROPIC_API_KEYを設定すると分析が利用できます。")
    else:
        st.caption(f"🔑 Claude APIキー：設定済み（値は表示しません）｜モデル：{model}")
    agree=st.checkbox("今回の分析データがAnthropicへ送信され、API料金が発生し得ることに同意する")
    payload={"book":book[:150],"objective":objective,"metrics":summary,"candidates":actions[:20]}
    with st.expander("AIへ送信する内容"):
        st.json(payload)
    if st.button("広告改善をClaudeで分析",disabled=not(api_key and agree)):
        st.session_state.pop("analysis",None)
        st.session_state.pop("claude_error",None)
        with st.spinner("Claudeに分析を依頼しています。完了までお待ちください..."):
            try:
                from anthropic import Anthropic
                result=Anthropic(api_key=api_key,timeout=30).messages.create(
                    model=model,max_tokens=1200,
                    system="日本のKindle広告の分析担当。入力データだけを事実とし、数字を創作しない。広告売上と印税の違い、直近14日の売上反映遅延に注意。広告設定は変更しない。日本語で優先順位と理由を示す。",
                    messages=[{"role":"user","content":json.dumps(payload,ensure_ascii=False)}])
                st.session_state.analysis="\n".join(x.text for x in result.content if x.type=="text").strip()
                if not st.session_state.analysis:
                    st.session_state.claude_error="API処理は完了しましたが、表示できる回答が空でした。"
            except Exception as e:
                code=getattr(e,"status_code",None)
                hints={400:"リクエスト設定",401:"APIキー",402:"API請求・残高",403:"アクセス権限",404:"モデル名・利用権限",429:"利用上限・API残高",529:"Anthropicの混雑"}
                hint=hints.get(code,"通信・API設定")
                st.session_state.claude_error=f"{type(e).__name__}／HTTP {code if code else 'なし'}。{hint}を確認してください。"
    if st.session_state.get("claude_error"):
        st.error("Claudeの分析が完了していません："+st.session_state.claude_error)
        st.caption("エラー表示にAPIキーなどの秘密情報は含めていません。秘密情報はチャットに送らないでください。")
    if st.session_state.get("analysis"):
        st.success("✅ Claudeの分析結果を受信しました。")
        st.markdown(st.session_state.analysis)
        st.download_button("分析文を保存",st.session_state.analysis,file_name="kindle_ai_report.txt")
    st.divider()
    memo=st.text_area("確認済みのキャンペーン条件（SNS原稿に反映）","発売記念価格と終了日時は投稿前に確認")
    if st.button("X投稿案を3本生成",disabled=not(api_key and agree)):
        try:
            from anthropic import Anthropic
            result=Anthropic(api_key=api_key,timeout=30).messages.create(
                model=model,max_tokens=700,
                system="高城直人の日本語X投稿編集者。YouTube登録者6万人の経験を紹介し、大人の副業・動画制作者に向けて自然な告知を作る。誇大な表現や架空の購入者・売上を作らない。投稿は手動。",
                messages=[{"role":"user","content":f"書籍：{book[:150]}。確認済み販売条件：{memo[:500]}。140文字以内で体験談・実務Tips・短いシュール系の3案"}])
            st.session_state.posts="\n".join(x.text for x in result.content if x.type=="text")
        except Exception as e:
            st.error(f"生成できませんでした：{type(e).__name__}")
    if st.session_state.get("posts"):
        st.text_area("編集してコピー・Xで手動投稿",st.session_state.posts,height=230)
with exports:
    snap={"generated_jst":datetime.now(JST).isoformat(),"book":book,"asin":asin,
          "price_jpy":price,"royalty_per_order_jpy":royalty,"objective":objective,
          "report_start":period_start.isoformat(),"report_end":period_end.isoformat(),
          "sample":bool(sample and not uploads),"metrics":summary,
          "kdp_total_orders_manual":kdp_orders,"actions":edited.to_dict("records"),
          "notice":"Amazon広告には反映していません。広告CSVとKDP実売上は別指標です。"}
    st.download_button("分析結果JSONを保存",json.dumps(snap,ensure_ascii=False,indent=2).encode(),file_name="kindle_marketing_report.json",mime="application/json")
    st.download_button("キャンペーン集計CSV",safe_csv(breakdown(primary,["campaign"])),file_name="kindle_campaign_metrics.csv",mime="text/csv")
st.caption("初期版 v0.1｜Amazon Ads API未接続｜広告自動変更なし｜データはセッション中のみ保持")
