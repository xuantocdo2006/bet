"""Dashboard phân tích bóng đá. Chạy: streamlit run app.py"""
import os

import pandas as pd
import streamlit as st

import analysis as A
import collector
import db
import demo_data

st.set_page_config(page_title="Phân tích bóng đá", page_icon="⚽", layout="wide")
st.title("⚽ Phân tích trận đấu bóng đá")

# ------------------------------------------------------------- thanh bên
with st.sidebar:
    st.header("Dữ liệu")
    comps = db.list_competitions()
    if comps:
        labels = {c: f"{c} ({n} trận)" for c, n in comps}
        competition = st.selectbox("Giải đấu", [c for c, _ in comps],
                                   format_func=lambda c: labels[c])
    else:
        competition = None
        st.info("Chưa có dữ liệu. Hãy thu thập từ API hoặc tạo dữ liệu demo.")

    with st.expander("Thu thập từ football-data.org", expanded=not comps):
        key = st.text_input("API key", type="password",
                            value=os.environ.get("FOOTBALL_DATA_API_KEY", ""),
                            help="Đăng ký miễn phí tại football-data.org")
        pick = st.multiselect("Giải", list(collector.COMPETITIONS),
                              default=["PL"],
                              format_func=lambda c: f"{c} - {collector.COMPETITIONS[c]}")
        seasons = st.multiselect("Mùa (năm bắt đầu)", [2026, 2025, 2024, 2023], default=[2025])
        if st.button("Thu thập dữ liệu", type="primary"):
            if not key:
                st.error("Vui lòng nhập API key.")
            elif not pick or not seasons:
                st.error("Chọn ít nhất một giải và một mùa.")
            else:
                msgs = []
                total = 0
                with st.spinner("Đang tải (giới hạn 10 request/phút nên có thể mất vài phút)..."):
                    try:
                        total = collector.collect(pick, seasons, token=key, log=msgs.append)
                    except Exception as e:  # hiển thị lỗi mạng/API thân thiện
                        msgs.append(f"❌ Lỗi: {e}")
                st.session_state["collect_msgs"] = msgs + [f"Tổng cộng đã lưu {total} trận."]
                st.rerun()
        for m in st.session_state.pop("collect_msgs", []):
            st.write(m)

    if st.button("Tạo dữ liệu demo"):
        demo_data.load_demo()
        st.rerun()

if not competition:
    st.stop()

df = db.load_matches(competition)
fin = A.finished(df)
if len(fin) < 30:
    st.warning("Cần ít nhất 30 trận đã đá để phân tích. Hãy thu thập thêm dữ liệu.")
    st.stop()

# Nếu dữ liệu chứa nhiều mùa, cho lọc
seasons_avail = sorted(df["season"].dropna().unique().astype(int).tolist(), reverse=True)
with st.sidebar:
    chosen = st.multiselect("Lọc mùa", seasons_avail, default=seasons_avail)
if chosen:
    df = df[df["season"].isin(chosen)]
    fin = A.finished(df)

teams = A.teams_of(fin)

tab_table, tab_form, tab_h2h, tab_stats, tab_pred, tab_bt = st.tabs(
    ["📊 Bảng xếp hạng", "📈 Phong độ", "🤝 Đối đầu", "🔎 Thống kê", "🎯 Dự đoán", "🧪 Kiểm chứng mô hình"])

# ---------------------------------------------------------- bảng xếp hạng
with tab_table:
    ov = A.league_overview(fin)
    cols = st.columns(len(ov))
    for c, (k, v) in zip(cols, ov.items()):
        c.metric(k, v)
    st.subheader("Bảng xếp hạng")
    st.dataframe(A.standings(fin), width="stretch", height=600)
    st.subheader("Xếp hạng Elo")
    st.dataframe(A.elo_ratings(fin).to_frame(), width="stretch")

# ---------------------------------------------------------------- phong độ
with tab_form:
    team = st.selectbox("Chọn đội", teams, key="form_team")
    n = st.slider("Số trận gần nhất", 3, 15, 5)
    s = A.form_summary(fin, team, n)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Chuỗi (T/H/B)", s["chuoi"])
    c2.metric("Điểm", f'{s["diem"]}/{s["diem_toi_da"]}')
    c3.metric("Bàn thắng TB", s["ban_thang_tb"])
    c4.metric("Bàn thua TB", s["ban_thua_tb"])
    recent = A.form(fin, team, n).copy()
    recent["date"] = recent["date"].dt.strftime("%d/%m/%Y")
    st.dataframe(recent[["date", "opponent", "venue", "gf", "ga", "result"]].rename(columns={
        "date": "Ngày", "opponent": "Đối thủ", "venue": "Sân", "gf": "BT", "ga": "BB",
        "result": "KQ"}), width="stretch", hide_index=True)
    roll = A.rolling_points(fin, team, window=n)
    st.caption(f"Điểm trung bình mỗi trận trong {n} trận gần nhất, theo thời gian")
    st.line_chart(roll.set_index("date")["diem_TB_gan_day"])

# ---------------------------------------------------------------- đối đầu
with tab_h2h:
    c1, c2 = st.columns(2)
    a = c1.selectbox("Đội A", teams, index=0, key="h2h_a")
    b = c2.selectbox("Đội B", teams, index=min(1, len(teams) - 1), key="h2h_b")
    if a == b:
        st.info("Hãy chọn hai đội khác nhau.")
    else:
        summary, h = A.head_to_head(fin, a, b)
        if summary["so_tran"] == 0:
            st.info("Hai đội chưa gặp nhau trong dữ liệu hiện có.")
        else:
            c = st.columns(4)
            c[0].metric("Số trận", summary["so_tran"])
            c[1].metric(f"{a} thắng", summary[f"{a} thắng"])
            c[2].metric("Hòa", summary["Hòa"])
            c[3].metric(f"{b} thắng", summary[f"{b} thắng"])
            st.caption(f"Tổng bàn thắng trung bình mỗi trận đối đầu: {summary['tong_ban_thang_tb']}")
            h = h.copy()
            h["utc_date"] = h["utc_date"].dt.strftime("%d/%m/%Y")
            st.dataframe(h.rename(columns={
                "utc_date": "Ngày", "home_team": "Chủ nhà", "home_goals": "BT chủ",
                "away_goals": "BT khách", "away_team": "Khách"}),
                width="stretch", hide_index=True)

# ---------------------------------------------------------------- thống kê
with tab_stats:
    team = st.selectbox("Chọn đội", teams, key="stat_team")
    stats = A.team_stats(fin, team)
    st.dataframe(pd.DataFrame(stats.items(), columns=["Chỉ số", "Giá trị"]),
                 width="stretch", hide_index=True)
    st.caption("Các chỉ số tính từ tỷ số (gồm tỷ số hiệp 1 nếu có). Số cú sút, kiểm soát bóng, "
               "thẻ phạt không có trong gói dữ liệu miễn phí.")
    with st.expander("So sánh toàn giải"):
        rows = []
        for t in teams:
            s = A.team_stats(fin, t)
            rows.append({"Đội": t, "BT TB": s["Bàn thắng TB/trận"], "BB TB": s["Bàn thua TB/trận"],
                         "Giữ sạch lưới %": s["Giữ sạch lưới (%)"],
                         "BTTS %": s["Cả hai đội ghi bàn - BTTS (%)"],
                         "Tài 2.5 %": s["Tài 2.5 bàn (%)"]})
        st.dataframe(pd.DataFrame(rows).sort_values("BT TB", ascending=False),
                     width="stretch", hide_index=True)

# ---------------------------------------------------------------- dự đoán
with tab_pred:
    st.caption("Mô hình Poisson có trọng số thời gian + Elo. Đây là ước lượng xác suất từ lịch sử, "
               "không phải kết quả chắc chắn.")
    xi = st.slider("Độ ưu tiên trận gần đây", 0.0, 0.01, 0.002, 0.0005,
                   help="Càng cao thì trận cũ càng ít ảnh hưởng.")
    model = A.fit_poisson(fin, xi=xi)
    ratings = A.elo_ratings(fin)

    c1, c2 = st.columns(2)
    home = c1.selectbox("Chủ nhà", teams, index=0, key="p_home")
    away = c2.selectbox("Đội khách", teams, index=min(1, len(teams) - 1), key="p_away")
    if home == away:
        st.info("Hãy chọn hai đội khác nhau.")
    else:
        p = A.predict_match(model, home, away)
        c = st.columns(3)
        c[0].metric(f"{home} thắng", f'{p["p_home"] * 100:.1f}%')
        c[1].metric("Hòa", f'{p["p_draw"] * 100:.1f}%')
        c[2].metric(f"{away} thắng", f'{p["p_away"] * 100:.1f}%')
        c = st.columns(4)
        c[0].metric("Bàn kỳ vọng (chủ)", f'{p["lam_home"]:.2f}')
        c[1].metric("Bàn kỳ vọng (khách)", f'{p["lam_away"]:.2f}')
        c[2].metric("Tài 2.5 bàn", f'{p["p_over25"] * 100:.1f}%')
        c[3].metric("Cả hai đội ghi bàn", f'{p["p_btts"] * 100:.1f}%')
        st.write("**Tỷ số khả dĩ nhất:** " + ", ".join(
            f"{i}-{j} ({pr * 100:.1f}%)" for i, j, pr in p["top_scores"]))
        e = A.elo_expectation(ratings, home, away)
        st.caption(f"Tham chiếu Elo: xác suất kỳ vọng của chủ nhà (hòa tính nửa điểm) = {e * 100:.1f}%")

    up = A.upcoming(df)
    if len(up):
        st.subheader("Các trận sắp diễn ra")
        rows = []
        for _, r in up.head(20).iterrows():
            try:
                p = A.predict_match(model, r.home_team, r.away_team)
            except ValueError:
                continue
            rows.append({"Ngày": r.utc_date.strftime("%d/%m/%Y"), "Chủ nhà": r.home_team,
                         "Khách": r.away_team, "% Chủ thắng": round(p["p_home"] * 100, 1),
                         "% Hòa": round(p["p_draw"] * 100, 1),
                         "% Khách thắng": round(p["p_away"] * 100, 1)})
        if rows:
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

# ---------------------------------------------------------------- backtest
with tab_bt:
    st.write("Kiểm tra mô hình: dự đoán lại các trận gần nhất chỉ bằng dữ liệu **trước** mỗi trận, "
             "rồi so với kết quả thật.")
    last_n = st.slider("Số trận kiểm tra", 30, 200, 80, 10)
    if st.button("Chạy kiểm chứng"):
        with st.spinner("Đang tính..."):
            summary, res = A.backtest(fin, last_n=last_n, xi=xi)
        if not summary:
            st.warning("Chưa đủ dữ liệu để kiểm chứng.")
        else:
            c = st.columns(4)
            c[0].metric("Số trận", summary["so_tran"])
            c[1].metric("Độ chính xác (T/H/B)", f'{summary["do_chinh_xac_%"]}%')
            c[2].metric("Log-loss mô hình", summary["log_loss"])
            c[3].metric("Log-loss đoán ngẫu nhiên", summary["log_loss_ngau_nhien"])
            st.caption(f"Chủ nhà thắng {summary['ti_le_chu_nha_thang_%']}% số trận này. "
                       "Log-loss càng thấp càng tốt; mô hình hữu ích khi thấp hơn mức ngẫu nhiên.")
