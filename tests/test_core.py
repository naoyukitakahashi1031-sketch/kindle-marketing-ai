from kma.core import read_csv, summarize, proposals, safe_csv
import pandas as pd

def test_reads_japanese_csv():
    r=read_csv("キャンペーン名,表示回数,クリック数,広告費,注文数,広告売上\nX,100,10,100,1,99\n".encode(),"ads.csv")
    assert r.kind=="キャンペーン"
    assert summarize(r.data,32)["indicative_margin"] == -68

def test_does_not_duplicate_report_levels():
    base="Campaign Name,Impressions,Clicks,Spend,Orders,Sales\nA,100,2,50,1,99\n"
    a=read_csv(base.encode(),"a.csv")
    assert summarize(a.data)["spend"] == 50

def test_new_data_waits_before_negative():
    r=read_csv("Campaign Name,Impressions,Clicks,Spend,Orders,Sales\nA,2000,15,500,0,0\n".encode(),"a.csv")
    assert "監視" in proposals(r.data,"キャンペーン",32,False)[-1]["recommendation"]

def test_csv_formula_escape():
    df=pd.DataFrame({"campaign":["=HYPERLINK(1)","safe"]})
    assert "'=HYPERLINK" in safe_csv(df).decode("utf-8-sig")
