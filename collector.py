"""Thu thập dữ liệu trận đấu từ football-data.org (API v4, gói miễn phí).

Đăng ký key miễn phí tại https://www.football-data.org/client/register
Gói miễn phí: giới hạn 10 request/phút và chỉ một số giải (PL, PD, BL1, SA, FL1, CL, ...).
Dữ liệu miễn phí gồm tỷ số cả trận, tỷ số hiệp 1, lịch thi đấu. Không có số cú sút,
kiểm soát bóng, thẻ phạt (các thống kê đó cần gói trả phí hoặc nguồn khác).
"""
import os
import sys
import time

import requests

import db

BASE_URL = "https://api.football-data.org/v4"
MIN_INTERVAL = 6.5  # giây giữa 2 request để không vượt 10 request/phút

COMPETITIONS = {
    "PL": "Premier League (Anh)",
    "PD": "La Liga (Tây Ban Nha)",
    "BL1": "Bundesliga (Đức)",
    "SA": "Serie A (Ý)",
    "FL1": "Ligue 1 (Pháp)",
    "CL": "UEFA Champions League",
    "ELC": "Championship (Anh)",
    "DED": "Eredivisie (Hà Lan)",
    "PPL": "Primeira Liga (Bồ Đào Nha)",
}


class CollectorError(RuntimeError):
    pass


def parse_match(m, competition, season):
    score = m.get("score") or {}
    full = score.get("fullTime") or {}
    half = score.get("halfTime") or {}
    return {
        "id": m["id"],
        "competition": competition,
        "season": season,
        "matchday": m.get("matchday"),
        "utc_date": m["utcDate"],
        "status": m.get("status"),
        "home_id": (m.get("homeTeam") or {}).get("id"),
        "home_team": (m.get("homeTeam") or {}).get("name") or "?",
        "away_id": (m.get("awayTeam") or {}).get("id"),
        "away_team": (m.get("awayTeam") or {}).get("name") or "?",
        "home_goals": full.get("home"),
        "away_goals": full.get("away"),
        "ht_home": half.get("home"),
        "ht_away": half.get("away"),
        "winner": score.get("winner"),
    }


def fetch_matches(competition, season, token, session=None, max_retries=3):
    """Lấy toàn bộ trận của một giải trong một mùa. season = năm bắt đầu (vd 2025)."""
    http = session or requests
    url = f"{BASE_URL}/competitions/{competition}/matches"
    for attempt in range(max_retries):
        resp = http.get(url, headers={"X-Auth-Token": token},
                        params={"season": season}, timeout=30)
        if resp.status_code == 429:  # quá giới hạn tốc độ
            wait = int(resp.headers.get("Retry-After", 60))
            time.sleep(wait + 1)
            continue
        if resp.status_code in (401, 403):
            raise CollectorError(
                f"{competition} {season}: API key sai hoặc gói miễn phí không có quyền "
                f"truy cập giải/mùa này (HTTP {resp.status_code}).")
        if resp.status_code == 404:
            raise CollectorError(f"{competition} {season}: không tìm thấy dữ liệu (404).")
        resp.raise_for_status()
        data = resp.json()
        return [parse_match(m, competition, season) for m in data.get("matches", [])]
    raise CollectorError(f"{competition} {season}: bị giới hạn tốc độ, thử lại sau ít phút.")


def collect(competitions, seasons, token=None, log=print):
    """Thu thập nhiều giải/mùa và lưu vào DB. Trả về tổng số trận đã lưu."""
    token = token or os.environ.get("FOOTBALL_DATA_API_KEY")
    if not token:
        raise CollectorError("Thiếu API key. Đặt biến môi trường FOOTBALL_DATA_API_KEY "
                             "hoặc nhập key trong ứng dụng.")
    total = 0
    first = True
    for comp in competitions:
        for season in seasons:
            if not first:
                time.sleep(MIN_INTERVAL)
            first = False
            try:
                rows = fetch_matches(comp, season, token)
            except CollectorError as e:
                log(f"⚠️ {e}")
                continue
            n = db.upsert_matches(rows)
            total += n
            log(f"✅ {comp} {season}: đã lưu {n} trận")
    return total


if __name__ == "__main__":
    # Ví dụ: python collector.py PL 2025 2024
    if len(sys.argv) < 3:
        print("Cách dùng: python collector.py <MÃ_GIẢI> <MÙA> [<MÙA> ...]")
        print("Mã giải:", ", ".join(COMPETITIONS))
        sys.exit(1)
    collect([sys.argv[1]], [int(s) for s in sys.argv[2:]])
