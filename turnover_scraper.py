
"""
2026 College Football Turnover Analysis

Analyzes turnovers lost per game against
winning percentage for FBS football teams.

Sources:
- CFBStats: Turnover Statistics
- D1SportsNet: Win-Loss Standings
"""

import re
from pathlib import Path

import requests
import pandas as pd
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup


# ==========================================
# SETTINGS
# ==========================================

SEASON = 2026

TURNOVER_URL = (
    "https://cfbstats.com/2026/leader/national/"
    "team/offense/split01/category12/sort08.html"
)

STANDINGS_URL = (
    "https://d1sportsnet.com/football/standings/"
)

OUTPUT = Path(__file__).resolve().parent / "results"
OUTPUT.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

MIN_TEAMS = 110


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    return BeautifulSoup(
        response.text,
        "html.parser"
    )


def number(value):
    value = str(value).replace(",", "").strip()

    if value.isdigit():
        return int(value)

    return None


def normalize_team(name):
    name = name.lower().strip()

    # Handle location-based school names first
    name = name.replace("miami (fl)", "miami florida")
    name = name.replace("miami (oh)", "miami ohio")

    name = re.sub(r"[^a-z0-9 ]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    aliases = {
        "usf": "south florida",
        "south fla": "south florida",
        "army": "army west point",
        "fla atlantic": "florida atlantic",
        "fla international": "florida international",
        "fiu": "florida international",
        "ucf": "central florida",
        "utsa": "texas san antonio",
        "uconn": "connecticut",
        "ole miss": "mississippi",
        "usc": "southern california",
        "nc state": "north carolina state",
        "penn st": "penn state",
        "florida st": "florida state",
        "florida st seminoles": "florida state",
        "boise st": "boise state",
        "fresno st": "fresno state",
        "oregon st": "oregon state",
        "ohio st": "ohio state",
        "michigan st": "michigan state",
        "arizona st": "arizona state",
        "kansas st": "kansas state",
        "iowa st": "iowa state",
        "oklahoma st": "oklahoma state",
        "colorado st": "colorado state",
        "utah st": "utah state",
        "ball st": "ball state",
        "kent st": "kent state",
        "texas st": "texas state",
        "san jose st": "san jose state",
        "san diego st": "san diego state",
        "washington st": "washington state",
        "georgia st": "georgia state",
        "ga southern": "georgia southern",
        "western mich": "western michigan",
        "eastern mich": "eastern michigan",
        "central mich": "central michigan",
        "western ky": "western kentucky",
        "middle tenn": "middle tennessee state",
        "middle tennessee": "middle tennessee state",
        "la tech": "louisiana tech",
        "missouri st": "missouri state",
        "north dakota st": "north dakota state",
        "new mexico st": "new mexico state",
        "sam houston": "sam houston state",
        "jacksonville st": "jacksonville state",
        "kennesaw st": "kennesaw state",
        "appalachian st": "appalachian state",
        "app state": "appalachian state",
        "sacramento st": "sacramento state",
        "northern illinois": "niu",
        "hawai i": "hawaii",
    }

    return aliases.get(name, name)


# ==========================================
# SCRAPE TURNOVER DATA
# ==========================================

def scrape_turnovers():
    print("Downloading 2026 turnover statistics...")

    soup = get_page(TURNOVER_URL)

    title = soup.get_text(" ", strip=True)

    if "2026 National Leaders" not in title:
        raise ValueError(
            "The turnover page is not the expected "
            "2026 national statistics page."
        )

    teams = []

    for table in soup.find_all("table"):

        table_text = table.get_text(" ", strip=True)

        if (
            "Total Lost" not in table_text
            or "Fum. Lost" not in table_text
        ):
            continue

        for row in table.find_all("tr"):

            cells = [
                cell.get_text(" ", strip=True)
                for cell in row.find_all("td")
            ]

            # Rank, Name, G, Fum Gain,
            # Int Gain, Total Gain,
            # Fum Lost, Int Lost,
            # Total Lost, Margin, Margin/G

            if len(cells) != 11:
                continue

            team = cells[1]

            games = number(cells[2])
            fumbles = number(cells[6])
            interceptions = number(cells[7])
            turnovers = number(cells[8])

            if any(
                x is None for x in [
                    games,
                    fumbles,
                    interceptions,
                    turnovers
                ]
            ):
                continue

            if games == 0:
                continue

            if fumbles + interceptions != turnovers:
                continue

            teams.append({
                "team": team,
                "team_key": normalize_team(team),
                "games": games,
                "fumbles_lost": fumbles,
                "interceptions_thrown": interceptions,
                "turnovers_lost": turnovers,
                "turnovers_per_game": turnovers / games
            })

    df = pd.DataFrame(teams)

    if df.empty:
        raise ValueError(
            "No turnover data found. "
            "Check the website table structure."
        )

    df = df.drop_duplicates(subset="team_key")

    print(f"Turnover teams collected: {len(df)}")

    return df


# ==========================================
# SCRAPE TEAM STANDINGS
# ==========================================

def scrape_standings():
    print("Downloading team standings...")

    soup = get_page(STANDINGS_URL)

    records = []

    for table in soup.find_all("table"):

        for row in table.find_all("tr"):

            cells = [
                cell.get_text(" ", strip=True)
                for cell in row.find_all("td")
            ]

            # School | Conf W | Conf L |
            # Overall W | Overall L | ...

            if len(cells) < 5:
                continue

            team = cells[0]
            wins = number(cells[3])
            losses = number(cells[4])

            if wins is None or losses is None:
                continue

            if wins + losses == 0:
                continue

            records.append({
                "team_key": normalize_team(team),
                "wins": wins,
                "losses": losses,
                "win_pct": wins / (wins + losses)
            })

    df = pd.DataFrame(records)

    if df.empty:
        raise ValueError("No standings were found.")

    df = df.drop_duplicates(subset="team_key")

    print(f"Standings collected: {len(df)}")

    return df


# ==========================================
# MERGE AND VALIDATE
# ==========================================

def analyze(turnovers, standings):

    df = turnovers.merge(
        standings,
        on="team_key",
        how="inner",
        validate="one_to_one"
    )

    print(f"Teams matched: {len(df)}")

    unmatched = turnovers[
        ~turnovers["team_key"].isin(
            standings["team_key"]
        )
    ]

    if not unmatched.empty:
        print("\nUnmatched schools:")
        print(unmatched["team"].to_string(index=False))

    if len(df) < MIN_TEAMS:
        raise ValueError(
            f"Only {len(df)} teams matched. "
            "Not enough for a full FBS analysis. "
            "Review the unmatched school names."
        )

    # Check that both sources cover the
    # same completed games for each team.
    df["record_games"] = df["wins"] + df["losses"]

    mismatched = df[
        df["games"] != df["record_games"]
    ]

    if not mismatched.empty:
        print("\nInconsistent game counts:")
        print(
            mismatched[
                ["team", "games", "wins", "losses"]
            ].to_string(index=False)
        )

        raise ValueError(
            "Some team records do not match "
            "the turnover reporting period."
        )

    if len(df) / len(turnovers) < 0.90:
        raise ValueError(
            "More than 10% of turnover teams "
            "failed to match standings."
        )

    df = df.sort_values(
        "turnovers_per_game",
        ascending=False
    ).reset_index(drop=True)

    correlation = df[
        "turnovers_per_game"
    ].corr(df["win_pct"])

    if pd.isna(correlation):
        raise ValueError(
            "Correlation could not be calculated."
        )

    print("\n" + "=" * 55)
    print("2026 COLLEGE FOOTBALL TURNOVER ANALYSIS")
    print("=" * 55)

    print(f"\nTeams analyzed: {len(df)}")

    print(
        f"Average turnovers lost per game: "
        f"{df['turnovers_per_game'].mean():.2f}"
    )

    print(
        f"Pearson correlation: {correlation:.3f}"
    )

    print(
        "\nReminder: Correlation does not "
        "prove causation."
    )

    print("\nTop 20 teams by turnovers lost per game:\n")

    print(
        df[
            [
                "team",
                "turnovers_lost",
                "turnovers_per_game",
                "wins",
                "losses",
                "win_pct"
            ]
        ].head(20).to_string(index=False)
    )

    df.drop(
        columns=["team_key", "record_games"]
    ).to_csv(
        OUTPUT / "cfb_2026_analysis.csv",
        index=False
    )

    return df, correlation


# ==========================================
# CHART 1: CORRELATION
# ==========================================

def create_scatterplot(df, correlation):

    x = df["turnovers_per_game"]
    y = df["win_pct"] * 100

    plt.figure(figsize=(11, 7))

    plt.scatter(
        x, y,
        color="#2563eb",
        alpha=0.65
    )

    slope = (
        ((x - x.mean()) * (y - y.mean())).sum()
        / ((x - x.mean()) ** 2).sum()
    )

    intercept = y.mean() - slope * x.mean()

    x_line = [x.min(), x.max()]
    y_line = [
        slope * value + intercept
        for value in x_line
    ]

    plt.plot(
        x_line,
        y_line,
        color="#dc2626",
        label="Linear trend"
    )

    plt.title(
        "2026 FBS: Turnovers Lost vs Win Percentage\n"
        f"Pearson r = {correlation:.3f}"
    )

    plt.xlabel("Turnovers Lost per Game")
    plt.ylabel("Winning Percentage (%)")
    plt.ylim(0, 105)

    plt.grid(alpha=0.2)
    plt.legend()
    plt.tight_layout()

    plt.savefig(
        OUTPUT / "turnovers_vs_winning.png",
        dpi=200
    )


# ==========================================
# CHART 2: TOP 20 TEAMS
# ==========================================

def create_bar_chart(df):

    top = df.head(20).sort_values(
        "turnovers_per_game"
    )

    plt.figure(figsize=(12, 9))

    bars = plt.barh(
        top["team"],
        top["turnovers_per_game"],
        color="#2563eb"
    )

    for bar, (_, row) in zip(
        bars,
        top.iterrows()
    ):

        record = f"{row['wins']}-{row['losses']}"

        plt.text(
            bar.get_width() + 0.02,
            bar.get_y() + bar.get_height() / 2,
            record,
            va="center",
            fontsize=9
        )

    plt.title(
        "2026 FBS: Most Turnovers Lost Per Game"
    )

    plt.xlabel("Turnovers Lost Per Game")
    plt.ylabel("Team")

    plt.xlim(
        0,
        top["turnovers_per_game"].max() * 1.25
    )

    plt.tight_layout()

    plt.savefig(
        OUTPUT / "top_20_turnovers.png",
        dpi=200
    )


# ==========================================
# MAIN PROGRAM
# ==========================================

def main():

    print("\n2026 COLLEGE FOOTBALL DATA ANALYSIS")
    print("----------------------------------")

    turnovers = scrape_turnovers()
    standings = scrape_standings()

    df, correlation = analyze(
        turnovers,
        standings
    )

    create_scatterplot(df, correlation)
    create_bar_chart(df)

    print("\nAnalysis completed successfully.")

    print(f"\nResults saved to: {OUTPUT}")

    print("\nGenerated files:")
    print("cfb_2026_analysis.csv")
    print("turnovers_vs_winning.png")
    print("top_20_turnovers.png")

    plt.show()


if __name__ == "__main__":
    main()
