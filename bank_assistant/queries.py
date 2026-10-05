# 合成進件。既有額度只寫在這張表，instruction 不准出現這個數字。
CASES = {
    "禾豐食品": {
        "name": "禾豐食品有限公司",
        "years": 11,
        "financials": "齊",
        "limit_wan": 300,
        "watchlist": "無",
        "registry": "無近期變更",
    },
    "北岸倉儲": {
        "name": "北岸倉儲",
        "years": None,
        "financials": "缺最新財簽",
        "limit_wan": None,
        "watchlist": "無",
        "registry": "無近期變更",
    },
    "山海貿易": {
        "name": "山海貿易",
        "years": None,
        "financials": None,
        "limit_wan": None,
        "watchlist": "命中",
        "registry": "無近期變更",
    },
    "新葉食品": {
        "name": "新葉食品",
        "years": None,
        "financials": "齊",
        "limit_wan": None,
        "watchlist": "無",
        "registry": "無近期變更",
    },
}


def _find(company: str) -> dict | None:
    name = company.strip()
    if not name:
        return None
    hits = [row for key, row in CASES.items() if name in key or key in name]
    if len(hits) != 1:
        return None
    return hits[0]


def _miss(company: str) -> dict:
    return {"found": False, "company": company}


def get_customer(company: str) -> dict:
    """查客戶主檔。問公司、成立年數、財簽是否齊全時呼叫。company 填公司名稱。"""
    row = _find(company)
    if row is None:
        return _miss(company)
    out = {"found": True, "公司": row["name"]}
    if row["years"] is not None:
        out["成立年數"] = row["years"]
    if row["financials"] is not None:
        out["財簽"] = row["financials"]
    return out


def get_exposure(company: str) -> dict:
    """查既有額度。問額度時呼叫。沒呼叫不准講數字。company 填公司名稱。"""
    row = _find(company)
    if row is None:
        return _miss(company)
    limit = row["limit_wan"]
    return {
        "found": True,
        "公司": row["name"],
        "既有額度萬元": limit if limit is not None else "無紀錄",
    }


def check_watchlist(company: str) -> dict:
    """查警示名單。問有沒有警示時呼叫。company 填公司名稱。"""
    row = _find(company)
    if row is None:
        return _miss(company)
    return {"found": True, "公司": row["name"], "警示": row["watchlist"]}


def get_registry(company: str) -> dict:
    """查變更登記。問主體有沒有變更時呼叫。company 填公司名稱。"""
    row = _find(company)
    if row is None:
        return _miss(company)
    return {"found": True, "公司": row["name"], "變更登記": row["registry"]}


def _check_cases() -> None:
    assert get_exposure("禾豐食品")["既有額度萬元"] == 300
    assert get_exposure("食品")["found"] is False
    assert check_watchlist("山海貿易")["警示"] == "命中"


_check_cases()
