"""robots.txt: user-agent, Allow/Disallow, wildcard *, $, Crawl-delay.

Matcher nhỏ cho URL ASCII của lab; không phải thư viện REP đầy đủ cho mọi URL Unicode.
Không lấy được robots thì bỏ qua host. Không tự theo redirect của robots.
"""
import re
from urllib.parse import urlsplit


class RobotsRules:
    def __init__(self, text, user_agent):
        groups, agents, rules, delay = [], [], [], 0.0
        has_directive = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            name, value = (part.strip() for part in line.split(":", 1))
            name = name.lower()
            if name == "user-agent":
                if has_directive:
                    groups.append((agents, rules, delay))
                    agents, rules, delay, has_directive = [], [], 0.0, False
                agents.append(value.lower())
            elif agents:
                has_directive = True
                if name in {"allow", "disallow"} and value:
                    rules.append((value, name == "allow"))
                elif name == "crawl-delay":
                    try:
                        delay = max(delay, float(value))
                    except ValueError:
                        pass
        if agents:
            groups.append((agents, rules, delay))
        agent = user_agent.split("/", 1)[0].lower()
        specific = [g for g in groups if any(a != "*" and a in agent for a in g[0])]
        if specific:
            best = max(len(a) for g in specific for a in g[0] if a != "*" and a in agent)
            chosen = [g for g in specific if any(len(a) == best and a in agent for a in g[0])]
        else:
            chosen = [g for g in groups if "*" in g[0]]
        self.rules = [rule for group in chosen for rule in group[1]]
        self.delay = max((g[2] for g in chosen), default=0.0)

    def allowed(self, url):
        p = urlsplit(url)
        target = p.path + ("?" + p.query if p.query else "")
        matched = []
        for pattern, allow in self.rules:
            anchored = pattern.endswith("$")
            body = pattern[:-1] if anchored else pattern
            regex = "^" + re.escape(body).replace(r"\*", ".*") + ("$" if anchored else "")
            if re.search(regex, target):
                matched.append((len(body.replace("*", "")), allow))
        # Longest match; Allow thắng nếu cùng độ dài.
        return max(matched)[1] if matched else True

