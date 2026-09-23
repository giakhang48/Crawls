from urllib.robotparser import RobotFileParser
import requests


def check_imdb(user_agent="SEG301-IMDb-Crawler/1.0", timeout=20):
    robots_url = "https://www.imdb.com/robots.txt"
    seed = "https://www.imdb.com/chart/top/"
    response = requests.get(robots_url, headers={"User-Agent": user_agent}, timeout=timeout)
    response.raise_for_status()
    rp = RobotFileParser()
    rp.set_url(robots_url)
    rp.parse(response.text.splitlines())
    allowed = rp.can_fetch(user_agent, seed)
    print("=" * 78)
    print("IMDb DIRECT-CRAWL POLICY CHECK")
    print("=" * 78)
    print(f"robots.txt : {robots_url}")
    print(f"Seed       : {seed}")
    print(f"User-Agent : {user_agent}")
    print(f"Decision   : {'ALLOW' if allowed else 'BLOCK'}")
    print("No bypass is attempted by this project.")
    print("=" * 78)
    return allowed
