"""Sinh dữ liệu giải đấu giả lập để thử phần mềm mà không cần API key."""
from datetime import datetime, timedelta, timezone

import numpy as np

import db

TEAMS = [
    "Hanoi Lions", "Saigon Tigers", "Danang Eagles", "Haiphong Sharks", "Hue Dragons",
    "Cantho Storm", "Nhatrang Waves", "Dalat Pines", "Vinh Falcons", "Quynhon Bulls",
    "Thanhhoa Wolves", "Namdinh Foxes", "Binhduong Rhinos", "Hatinh Bears",
    "Baria Panthers", "Pleiku Hawks", "Thainguyen Steel", "Bacninh Knights",
    "Longan Cobras", "Tiengiang Pelicans",
]


def generate(seed=7, played_fraction=0.9, competition="DEMO", season=2025):
    rng = np.random.default_rng(seed)
    n = len(TEAMS)
    attack = rng.normal(0, 0.28, n)
    defence = rng.normal(0, 0.25, n)
    home_adv = 0.25
    base = 0.25

    pairs = [(i, j) for i in range(n) for j in range(n) if i != j]
    rng.shuffle(pairs)
    start = datetime(2025, 8, 9, 15, 0, tzinfo=timezone.utc)
    cutoff = int(len(pairs) * played_fraction)

    rows = []
    for k, (i, j) in enumerate(pairs):
        date = start + timedelta(days=k // 10 * 3.5)
        lam_h = np.exp(base + home_adv + attack[i] - defence[j])
        lam_a = np.exp(base + attack[j] - defence[i])
        played = k < cutoff
        hg = ag = hth = hta = winner = None
        status = "SCHEDULED"
        if played:
            hg, ag = int(rng.poisson(lam_h)), int(rng.poisson(lam_a))
            hth = int(rng.binomial(hg, 0.45))
            hta = int(rng.binomial(ag, 0.45))
            winner = "HOME_TEAM" if hg > ag else "AWAY_TEAM" if ag > hg else "DRAW"
            status = "FINISHED"
        rows.append({
            "id": 900000 + k, "competition": competition, "season": season,
            "matchday": k // 10 + 1, "utc_date": date.isoformat().replace("+00:00", "Z"),
            "status": status,
            "home_id": i, "home_team": TEAMS[i], "away_id": j, "away_team": TEAMS[j],
            "home_goals": hg, "away_goals": ag, "ht_home": hth, "ht_away": hta,
            "winner": winner,
        })
    return rows


def load_demo(path=db.DB_PATH):
    rows = generate()
    db.clear_competition("DEMO", path)
    return db.upsert_matches(rows, path)


if __name__ == "__main__":
    print(f"Đã tạo {load_demo()} trận demo")
