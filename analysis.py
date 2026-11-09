"""Phân tích trận đấu: bảng xếp hạng, phong độ, đối đầu, thống kê, Elo, dự đoán Poisson."""
import math
from collections import defaultdict

import numpy as np
import pandas as pd

MAX_GOALS = 8


# ---------------------------------------------------------------- tiện ích
def finished(df):
    """Chỉ giữ các trận đã kết thúc và có tỷ số."""
    if df.empty:
        return df
    d = df[df["home_goals"].notna() & df["away_goals"].notna()].copy()
    d["home_goals"] = d["home_goals"].astype(int)
    d["away_goals"] = d["away_goals"].astype(int)
    return d.sort_values("utc_date").reset_index(drop=True)


def upcoming(df):
    if df.empty:
        return df
    return df[df["home_goals"].isna()].sort_values("utc_date").reset_index(drop=True)


def teams_of(df):
    return sorted(set(df["home_team"]) | set(df["away_team"]))


def team_matches(df, team):
    """Đổi sang dạng 'một dòng = một trận của đội' (gf, ga, sân nhà/khách, kết quả)."""
    d = finished(df)
    h = d[d["home_team"] == team]
    a = d[d["away_team"] == team]
    home = pd.DataFrame({
        "date": h["utc_date"], "opponent": h["away_team"], "venue": "Nhà",
        "gf": h["home_goals"], "ga": h["away_goals"],
        "gf_ht": h["ht_home"], "ga_ht": h["ht_away"]})
    away = pd.DataFrame({
        "date": a["utc_date"], "opponent": a["home_team"], "venue": "Khách",
        "gf": a["away_goals"], "ga": a["home_goals"],
        "gf_ht": a["ht_away"], "ga_ht": a["ht_home"]})
    out = pd.concat([home, away]).sort_values("date").reset_index(drop=True)
    out["result"] = np.where(out.gf > out.ga, "T", np.where(out.gf < out.ga, "B", "H"))
    out["points"] = out["result"].map({"T": 3, "H": 1, "B": 0})
    return out


# ------------------------------------------------------ bảng xếp hạng
def standings(df):
    d = finished(df)
    recs = []
    for t in teams_of(d):
        m = team_matches(d, t)
        recs.append({
            "Đội": t, "Trận": len(m),
            "Thắng": int((m.result == "T").sum()), "Hòa": int((m.result == "H").sum()),
            "Thua": int((m.result == "B").sum()),
            "BT": int(m.gf.sum()), "BB": int(m.ga.sum()),
            "HS": int(m.gf.sum() - m.ga.sum()), "Điểm": int(m.points.sum()),
        })
    table = pd.DataFrame(recs)
    if table.empty:
        return table
    table = table.sort_values(["Điểm", "HS", "BT"], ascending=False).reset_index(drop=True)
    table.index += 1
    table.index.name = "Hạng"
    return table


# ------------------------------------------------------------ phong độ
def form(df, team, n=5):
    m = team_matches(df, team).tail(n)
    return m


def form_summary(df, team, n=5):
    m = form(df, team, n)
    if m.empty:
        return {}
    return {
        "chuoi": "".join(m.result),
        "diem": int(m.points.sum()),
        "diem_toi_da": 3 * len(m),
        "ban_thang_tb": round(m.gf.mean(), 2),
        "ban_thua_tb": round(m.ga.mean(), 2),
    }


def rolling_points(df, team, window=5):
    m = team_matches(df, team)
    m["diem_TB_gan_day"] = m.points.rolling(window, min_periods=1).mean()
    return m


# ------------------------------------------------------------ đối đầu
def head_to_head(df, a, b):
    d = finished(df)
    h = d[((d.home_team == a) & (d.away_team == b)) | ((d.home_team == b) & (d.away_team == a))]
    h = h.sort_values("utc_date", ascending=False)
    wa = wb = draws = 0
    for _, r in h.iterrows():
        ga = r.home_goals if r.home_team == a else r.away_goals
        gb = r.away_goals if r.home_team == a else r.home_goals
        if ga > gb:
            wa += 1
        elif gb > ga:
            wb += 1
        else:
            draws += 1
    summary = {"so_tran": len(h), f"{a} thắng": wa, f"{b} thắng": wb, "Hòa": draws,
               "tong_ban_thang_tb": round((h.home_goals + h.away_goals).mean(), 2) if len(h) else None}
    return summary, h[["utc_date", "home_team", "home_goals", "away_goals", "away_team"]]


# ------------------------------------------------------------ thống kê
def team_stats(df, team):
    """Thống kê chi tiết có thể tính từ dữ liệu tỷ số (không cần số cú sút...)."""
    m = team_matches(df, team)
    if m.empty:
        return {}
    n = len(m)
    total = m.gf + m.ga
    stats = {
        "Số trận": n,
        "Bàn thắng TB/trận": round(m.gf.mean(), 2),
        "Bàn thua TB/trận": round(m.ga.mean(), 2),
        "Giữ sạch lưới (%)": round((m.ga == 0).mean() * 100, 1),
        "Không ghi bàn (%)": round((m.gf == 0).mean() * 100, 1),
        "Cả hai đội ghi bàn - BTTS (%)": round(((m.gf > 0) & (m.ga > 0)).mean() * 100, 1),
        "Tài 2.5 bàn (%)": round((total > 2.5).mean() * 100, 1),
        "Tài 1.5 bàn (%)": round((total > 1.5).mean() * 100, 1),
    }
    for venue in ("Nhà", "Khách"):
        v = m[m.venue == venue]
        if len(v):
            stats[f"Điểm TB/trận ({venue})"] = round(v.points.mean(), 2)
            stats[f"Bàn thắng TB ({venue})"] = round(v.gf.mean(), 2)
            stats[f"Bàn thua TB ({venue})"] = round(v.ga.mean(), 2)
    ht = m.dropna(subset=["gf_ht", "ga_ht"])
    if len(ht):
        first = ht.gf_ht.sum() + ht.ga_ht.sum()
        all_goals = ht.gf.sum() + ht.ga.sum()
        if all_goals:
            stats["Tỷ lệ bàn ở hiệp 1 (%)"] = round(first / all_goals * 100, 1)
        led_ht = ht[ht.gf_ht > ht.ga_ht]
        if len(led_ht):
            stats["Giữ được thắng khi dẫn hiệp 1 (%)"] = round((led_ht.gf > led_ht.ga).mean() * 100, 1)
    return stats


def league_overview(df):
    d = finished(df)
    if d.empty:
        return {}
    total = d.home_goals + d.away_goals
    return {
        "Số trận đã đá": len(d),
        "Bàn thắng TB/trận": round(total.mean(), 2),
        "Thắng sân nhà (%)": round((d.home_goals > d.away_goals).mean() * 100, 1),
        "Hòa (%)": round((d.home_goals == d.away_goals).mean() * 100, 1),
        "Thắng sân khách (%)": round((d.home_goals < d.away_goals).mean() * 100, 1),
        "Tài 2.5 bàn (%)": round((total > 2.5).mean() * 100, 1),
        "BTTS (%)": round(((d.home_goals > 0) & (d.away_goals > 0)).mean() * 100, 1),
    }


# ---------------------------------------------------------------- Elo
def elo_ratings(df, k=20, home_adv=60, start=1500):
    d = finished(df)
    r = defaultdict(lambda: float(start))
    for _, row in d.iterrows():
        h, a = row.home_team, row.away_team
        exp_h = 1 / (1 + 10 ** ((r[a] - (r[h] + home_adv)) / 400))
        diff = row.home_goals - row.away_goals
        s = 1.0 if diff > 0 else 0.0 if diff < 0 else 0.5
        mult = math.log(abs(diff) + 1) + 1 if diff else 1.0
        delta = k * mult * (s - exp_h)
        r[h] += delta
        r[a] -= delta
    s = pd.Series(dict(r), name="Elo").sort_values(ascending=False)
    return s.round(1)


# ------------------------------------------------------- mô hình Poisson
def fit_poisson(df, xi=0.002, shrink=5.0, ref_date=None):
    """Ước lượng sức tấn công/phòng thủ từng đội (nhà/khách riêng).

    xi: hệ số giảm trọng số theo thời gian (mỗi ngày). Trận càng cũ trọng số càng nhỏ.
    shrink: số 'trận giả định' kéo sức mạnh về mức trung bình giải, chống quá khớp.
    """
    d = finished(df)
    if len(d) < 30:
        raise ValueError("Cần ít nhất 30 trận đã đá để huấn luyện mô hình.")
    ref = ref_date or d["utc_date"].max()
    days = (ref - d["utc_date"]).dt.total_seconds() / 86400
    w = np.exp(-xi * days.clip(lower=0))
    d = d.assign(w=w, hgw=d.home_goals * w, agw=d.away_goals * w)

    avg_h = d.hgw.sum() / d.w.sum()
    avg_a = d.agw.sum() / d.w.sum()
    h = d.groupby("home_team").agg(n=("w", "sum"), gf=("hgw", "sum"), ga=("agw", "sum"))
    a = d.groupby("away_team").agg(n=("w", "sum"), gf=("agw", "sum"), ga=("hgw", "sum"))
    k = shrink
    return {
        "avg_h": avg_h, "avg_a": avg_a,
        "att_h": (h.gf + k * avg_h) / ((h.n + k) * avg_h),
        "def_h": (h.ga + k * avg_a) / ((h.n + k) * avg_a),
        "att_a": (a.gf + k * avg_a) / ((a.n + k) * avg_a),
        "def_a": (a.ga + k * avg_h) / ((a.n + k) * avg_h),
    }


def _pmf(lam, kmax=MAX_GOALS):
    return np.array([math.exp(-lam) * lam ** i / math.factorial(i) for i in range(kmax + 1)])


def predict_match(model, home, away):
    for t in (home, away):
        if t not in model["att_h"].index and t not in model["att_a"].index:
            raise ValueError(f"Chưa có dữ liệu cho đội {t}")
    g = lambda s, t: float(s.get(t, 1.0))
    lam_h = model["avg_h"] * g(model["att_h"], home) * g(model["def_a"], away)
    lam_a = model["avg_a"] * g(model["att_a"], away) * g(model["def_h"], home)
    mat = np.outer(_pmf(lam_h), _pmf(lam_a))
    mat /= mat.sum()
    idx = np.indices(mat.shape)
    p_home = float(mat[idx[0] > idx[1]].sum())
    p_draw = float(np.trace(mat))
    p_away = float(mat[idx[0] < idx[1]].sum())
    total = idx[0] + idx[1]
    top = sorted(((int(i), int(j), float(mat[i, j])) for i in range(mat.shape[0])
                  for j in range(mat.shape[1])), key=lambda x: -x[2])[:5]
    return {
        "lam_home": lam_h, "lam_away": lam_a,
        "p_home": p_home, "p_draw": p_draw, "p_away": p_away,
        "p_over25": float(mat[total > 2.5].sum()),
        "p_btts": float(mat[1:, 1:].sum()),
        "top_scores": top, "matrix": mat,
    }


def elo_expectation(ratings, home, away, home_adv=60):
    rh, ra = ratings.get(home, 1500.0), ratings.get(away, 1500.0)
    return 1 / (1 + 10 ** ((ra - (rh + home_adv)) / 400))


# ------------------------------------------------------------ backtest
def backtest(df, last_n=100, min_train=100, **fit_kwargs):
    """Dự đoán từng trận gần nhất chỉ bằng dữ liệu TRƯỚC trận đó (không nhìn trước kết quả)."""
    d = finished(df)
    start = max(min_train, len(d) - last_n)
    recs = []
    for i in range(start, len(d)):
        row = d.iloc[i]
        train = d.iloc[:i]
        train = train[train["utc_date"] < row.utc_date]
        if len(train) < 30:
            continue
        try:
            model = fit_poisson(train, ref_date=row.utc_date, **fit_kwargs)
            p = predict_match(model, row.home_team, row.away_team)
        except ValueError:
            continue
        probs = np.array([p["p_home"], p["p_draw"], p["p_away"]])
        actual = 0 if row.home_goals > row.away_goals else 1 if row.home_goals == row.away_goals else 2
        recs.append({"actual": actual, "pred": int(probs.argmax()),
                     "p_actual": float(probs[actual]),
                     "ph": probs[0], "pd": probs[1], "pa": probs[2]})
    res = pd.DataFrame(recs)
    if res.empty:
        return {}, res
    base_h = (res.actual == 0).mean()
    summary = {
        "so_tran": len(res),
        "do_chinh_xac_%": round((res.pred == res.actual).mean() * 100, 1),
        "log_loss": round(float(-np.log(res.p_actual.clip(1e-9)).mean()), 4),
        "log_loss_ngau_nhien": round(math.log(3), 4),
        "ti_le_chu_nha_thang_%": round(base_h * 100, 1),
    }
    return summary, res
