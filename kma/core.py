"""Read-only Amazon Ads CSV normalisation, aggregation and conservative suggestions."""
from __future__ import annotations
import csv
import io
import re
import unicodedata
from dataclasses import dataclass
import pandas as pd

ALIASES = {
    "campaign": ["campaign name", "campaign", "キャンペーン名", "キャンペーン"],
    "search_term": ["customer search term", "search term", "search terms", "検索用語", "検索語句", "購入者の検索用語"],
    "target": ["targeting", "targeting expression", "keyword", "keyword text", "target", "ターゲティング", "キーワード"],
    "impressions": ["impressions", "impression", "インプレッション数", "表示回数", "インプレッション"],
    "clicks": ["clicks", "click", "クリック数", "クリック"],
    "spend": ["spend", "cost", "total cost", "広告費", "広告費用", "費用", "合計費用", "広告費（現地通貨）"],
    "orders": ["7 day total orders (#)", "14 day total orders (#)", "7 day total orders", "14 day total orders", "orders", "total orders", "purchases", "注文数", "注文", "購入数", "合計注文数"],
    "sales": ["7 day total sales", "14 day total sales", "7 day total sales (¥)", "14 day total sales (¥)", "sales", "attributed sales", "total sales", "売上", "売上高", "売上金額", "広告売上", "合計売上"],
    "bid": ["bid", "default bid", "keyword bid", "入札額", "入札単価"],
}
METRICS = ["impressions", "clicks", "spend", "orders", "sales"]
def _key(s):
    return re.sub(r"[^\w]", "", unicodedata.normalize("NFKC", str(s)).casefold()).replace("_","")
LOOKUP = {_key(alias): canonical for canonical, aliases in ALIASES.items() for alias in aliases}

@dataclass
class Report:
    name: str
    kind: str
    data: pd.DataFrame
    warnings: list[str]

def _number(s):
    s = s.fillna("").astype(str).str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    s = s.str.replace(r"[,，￥¥$€£%\s]", "", regex=True).str.replace(r"[^0-9.\-]", "", regex=True)
    return pd.to_numeric(s, errors="coerce").fillna(0).clip(lower=0)

def read_csv(data: bytes, filename: str) -> Report:
    if len(data) > 8_000_000:
        raise ValueError("CSVは8MBまでにしてください。")
    content = None
    for codec in ("utf-8-sig", "utf-16", "cp932", "shift_jis"):
        try:
            content = data.decode(codec)
            break
        except UnicodeError:
            continue
    if content is None:
        raise ValueError("文字コードを認識できません。")
    sample = "\n".join(content.splitlines()[:12])
    try:
        sep = csv.Sniffer().sniff(sample, delimiters=",\t;").delimiter
    except csv.Error:
        sep = "\t" if sample.count("\t") > sample.count(",") else ","
    frame = None
    for skip in range(8):
        try:
            trial = pd.read_csv(io.StringIO(content), sep=sep, skiprows=skip, dtype=str, on_bad_lines="skip")
            if sum(_key(col) in LOOKUP for col in trial.columns) >= 2:
                frame = trial
                break
        except (ValueError, pd.errors.ParserError):
            pass
    if frame is None:
        raise ValueError("Amazon広告のCSV列を認識できません。")
    renamed = {}
    discovered = set()
    for col in frame.columns:
        c = LOOKUP.get(_key(col))
        if c and c not in discovered:
            renamed[col] = c
            discovered.add(c)
    frame = frame.rename(columns=renamed)
    if not (discovered & {"impressions", "clicks", "spend", "orders"}):
        raise ValueError("実績列がありません。")
    kind = "検索語句" if "search_term" in discovered else ("ターゲティング" if "target" in discovered else "キャンペーン")
    warnings = []
    if "campaign" not in frame:
        frame["campaign"] = "（キャンペーン不明）"
        warnings.append("キャンペーン列なし。書籍別の集計に注意してください。")
    for metric in METRICS + ["bid"]:
        if metric in frame:
            frame[metric] = _number(frame[metric])
        else:
            frame[metric] = 0.0
            if metric != "bid":
                warnings.append(f"{metric} 列がなく、0扱いです。")
    for field in ["campaign", "search_term", "target"]:
        if field in frame:
            frame[field] = frame[field].fillna("").astype(str).str.strip()
    frame = frame.loc[frame[METRICS].sum(axis=1) > 0].copy()
    return Report(filename, kind, frame, warnings)

def summarize(df: pd.DataFrame, royalty: float = 0) -> dict:
    x = {field: float(df[field].sum()) for field in METRICS}
    x.update(
        ctr=100*x["clicks"]/x["impressions"] if x["impressions"] else 0,
        cpc=x["spend"]/x["clicks"] if x["clicks"] else 0,
        cvr=100*x["orders"]/x["clicks"] if x["clicks"] else 0,
        acos=100*x["spend"]/x["sales"] if x["sales"] else None,
        indicative_royalty=x["orders"]*royalty,
        indicative_margin=x["orders"]*royalty-x["spend"],
    )
    return x

def breakdown(df: pd.DataFrame, fields: list[str]) -> pd.DataFrame:
    result = df.groupby(fields, dropna=False, as_index=False)[METRICS].sum()
    result["CTR(%)"] = (result.clicks/result.impressions.where(result.impressions>0)*100).fillna(0)
    result["CPC(円)"] = (result.spend/result.clicks.where(result.clicks>0)).fillna(0)
    result["CVR(%)"] = (result.orders/result.clicks.where(result.clicks>0)*100).fillna(0)
    return result

def proposals(df: pd.DataFrame, scope: str, royalty: float, settled: bool) -> list[dict]:
    out = []
    grouping = ["campaign"]
    if scope == "検索語句":
        grouping.append("search_term")
    elif scope == "ターゲティング":
        grouping.append("target")
    for _, r in breakdown(df, grouping).iterrows():
        c, clicks, spend, orders, impressions = str(r["campaign"]), float(r.clicks), float(r.spend), float(r.orders), float(r.impressions)
        target = str(r.get("search_term", r.get("target", "")))
        def add(priority, action, evidence):
            out.append(dict(priority=priority, type=scope, campaign=c, target=target, recommendation=action, evidence=evidence, decision="未判断"))
        if impressions >= 500 and (clicks/impressions) < .0025:
            add("中", "検索意図・商品ページを確認", f"{int(impressions)}表示、CTR{100*clicks/impressions:.2f}%")
        if clicks >= 12 and orders == 0 and spend >= max(150, royalty*3):
            action = "除外・減額候補を手動検討" if settled else "帰属売上確定まで監視"
            add("高" if settled else "中", action, f"{int(clicks)}クリック、広告費¥{spend:.0f}、広告注文0。反映遅延に注意")
        if orders > 0 and royalty > 0 and spend > orders*royalty*1.5:
            add("中", "採算優先なら入札額・対象を精査", f"広告費¥{spend:.0f}、注文×印税概算¥{orders*royalty:.0f}。ランキング目的なら別判断")
        if settled and orders >= 3 and royalty > 0 and spend < orders*royalty*.6:
            add("低", "効率的な検索語句の拡張を検討", f"注文{int(orders)}件、広告費¥{spend:.0f}")
    return sorted(out, key=lambda x: {"高":0, "中":1, "低":2}[x["priority"]])

def safe_csv(df: pd.DataFrame) -> bytes:
    """Prevent spreadsheet formula execution when opening exported CSVs."""
    result = df.copy()
    for field in result.select_dtypes(include=["object","str"]).columns:
        result[field] = result[field].apply(
            lambda v: "'"+v if isinstance(v,str) and v.lstrip().startswith(("=","+","-","@")) else v
        )
    return result.to_csv(index=False).encode("utf-8-sig")
