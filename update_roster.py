#!/usr/bin/env python3
"""Refresh senators and committee rosters in people.json from the unitedstates/congress-legislators dataset.

Runs weekly in GitHub Actions (see .github/workflows/roster.yml) and right after a new Congress is sworn in.
It keeps every editorial field already in people.json (priority, why, record, state assets, staff rows, sources)
and only replaces the structural facts: who is a senator, party, state, committee seats and leadership roles.
New senators get priority 2 and a note to review. Departed senators are dropped from the roster (their notes
remain in the database under their id and can be exported).

Data: https://github.com/unitedstates/congress-legislators (public domain), files legislators-current.yaml,
committees-current.yaml, committee-membership-current.yaml. Requires PyYAML.
"""
import json, re, sys, os, unicodedata, urllib.request
from datetime import date
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PEOPLE = f"{ROOT}/people.json"
BASE = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/"
TIER3 = {"SSEG", "SSEV", "SSAP", "SSAS"}
TIER2 = {"SSFR", "SSFI", "SSCM", "SSGA", "SSBU"}
NUCLEAR_SUBS = {("SSEG", "Energy"), ("SSEV", "Clean Air, Climate, and Nuclear Innovation and Safety"), ("SSAP", "Energy and Water Development"), ("SSAS", "Strategic Forces")}
PSEUDO = {("SSAP", "Energy and Water Development"): "SSAP-EW", ("SSAS", "Strategic Forces"): "SSAS-SF", ("SSEV", "Clean Air, Climate, and Nuclear Innovation and Safety"): "SSEV-NUC", ("SSEG", "Energy"): "SSEG-EN"}


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SenateNuclearMap roster updater"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def main():
    data = json.load(open(PEOPLE, encoding="utf-8"))
    legislators = yaml.safe_load(get(BASE + "legislators-current.yaml"))
    committees = yaml.safe_load(get(BASE + "committees-current.yaml"))
    membership = yaml.safe_load(get(BASE + "committee-membership-current.yaml"))

    # --- senators ---
    sens = []
    for L in legislators:
        term = L["terms"][-1]
        if term.get("type") != "sen":
            continue
        last = L["name"].get("last", "")
        state = term["state"]
        sid = f"sen-{slug(last)}-{state.lower()}"
        party = {"Republican": "R", "Democrat": "D"}.get(term.get("party"), "I")
        first_sen = min(int(t["start"][:4]) for t in L["terms"] if t.get("type") == "sen")
        name = L["name"].get("official_full") or (L["name"].get("first", "") + " " + last).strip()
        sens.append({"id": sid, "name": name, "state": state, "party": party, "since": first_sen, "bioguide": L["id"].get("bioguide", ""), "leadership": term.get("leadership_title") or ""})
    if len(sens) < 95:
        print(f"error: only {len(sens)} senators parsed; aborting", file=sys.stderr)
        sys.exit(2)
    by_bio = {s["bioguide"]: s for s in sens}

    # --- committees (Senate only) ---
    clist = []
    for c in committees:
        if c.get("type") not in ("senate", "joint"):
            continue
        code = c["thomas_id"]
        tier = 3 if code in TIER3 else 2 if code in TIER2 else 1
        subs = []
        for sc in c.get("subcommittees", []):
            name = sc["name"]
            subs.append({"name": name, "thomas": code + sc["thomas_id"], "code": code + ":" + slug(name)[:40].rstrip("-"), "chair": None, "ranking": None, "members": [], "ex_officio": [], "nuclear_tier": 3 if (code, name) in NUCLEAR_SUBS else 0})
        clist.append({"code": code, "name": c["name"].replace("Senate Committee on ", "").replace("Joint Committee on ", "Joint Committee on "), "type": "joint" if c.get("type") == "joint" else ("standing" if not c["name"].lower().startswith(("select", "special")) else ("select" if "select" in c["name"].lower() else "special")), "jurisdiction": "", "nuclear_relevance": "", "nuclear_tier": tier, "chair": None, "ranking": None, "vice_chair": None, "members": [], "source": c.get("url", ""), "subcommittees": subs, "notes": ""})
    # carry over editorial text for committees we already describe
    old_c = {c["code"]: c for c in data.get("committee_list", [])}
    for c in clist:
        if c["code"] in old_c:
            for k in ("jurisdiction", "nuclear_relevance", "notes", "type"):
                c[k] = old_c[c["code"]].get(k, c[k])
    by_code = {c["code"]: c for c in clist}
    sub_by_thomas = {s["thomas"]: (c, s) for c in clist for s in c["subcommittees"]}

    for thomas, members in membership.items():
        if thomas in by_code:
            c = by_code[thomas]
            for m in members:
                s = by_bio.get(m.get("bioguide"))
                if not s:
                    continue
                c["members"].append(s["id"])
                t = (m.get("title") or "").lower()
                if "chair" in t and "vice" not in t and "ranking" not in t:
                    c["chair"] = s["id"]
                elif "vice" in t:
                    c["vice_chair"] = s["id"]
                elif "ranking" in t:
                    c["ranking"] = s["id"]
        elif thomas in sub_by_thomas:
            c, sc = sub_by_thomas[thomas]
            for m in members:
                s = by_bio.get(m.get("bioguide"))
                if not s:
                    continue
                sc["members"].append(s["id"])
                t = (m.get("title") or "").lower()
                if "chair" in t and "ranking" not in t:
                    sc["chair"] = s["id"]
                elif "ranking" in t:
                    sc["ranking"] = s["id"]
    for c in clist:
        if c["ranking"] is None and c["vice_chair"]:
            c["ranking"] = c["vice_chair"]
        c["member_count"] = len(c["members"])

    # --- roles per senator ---
    roles = {}
    for c in clist:
        for m in c["members"]:
            role = "Chair" if m == c["chair"] else ("Vice Chair" if m == c.get("vice_chair") else ("Ranking Member" if m == c["ranking"] else "Member"))
            e = {"code": c["code"], "name": c["name"], "type": c["type"], "role": role, "tier": c["nuclear_tier"], "subcommittees": []}
            for sc in c["subcommittees"]:
                if m in sc["members"]:
                    e["subcommittees"].append({"name": sc["name"], "code": sc["code"], "role": "Chair" if m == sc["chair"] else ("Ranking Member" if m == sc["ranking"] else "Member"), "tier": sc["nuclear_tier"]})
            roles.setdefault(m, []).append(e)

    # --- merge into people.json ---
    old = {p["id"]: p for p in data["people"]}
    # tolerate id drift (e.g. a dataset that spells a surname differently): match an existing senator of the same state by last-name token
    for s in sens:
        if s["id"] not in old:
            tok = slug(s["name"].split()[-1])
            cands = [pid for pid, q in old.items() if q.get("kind") == "senator" and q.get("state") == s["state"] and (pid.endswith("-" + tok + "-" + s["state"].lower()) or ("-" + tok + "-") in pid)]
            if len(cands) == 1:
                s["id"] = cands[0]
    by_bio = {s["bioguide"]: s for s in sens}
    people = []
    added, kept, removed = [], [], []
    for s in sens:
        p = old.get(s["id"])
        r = sorted(roles.get(s["id"], []), key=lambda e: (-e["tier"], {"Chair": 0, "Vice Chair": 1, "Ranking Member": 1, "Member": 2}[e["role"]], e["name"]))
        codes = [e["code"] for e in r]
        for e in r:
            for sc in e["subcommittees"]:
                codes.append(sc["code"])
                if (e["code"], sc["name"]) in PSEUDO:
                    codes.append(PSEUDO[(e["code"], sc["name"])])
        lead_bits = [e["role"] + ", " + e["name"] for e in r if e["role"] != "Member"] + [sc["role"] + ", " + e["name"] + " — " + sc["name"] for e in r for sc in e["subcommittees"] if sc["role"] in ("Chair", "Ranking Member")]
        if p:
            kept.append(s["id"])
            p.update({"name": s["name"], "state": s["state"], "party": s["party"], "since": s["since"], "committees": codes, "roles": r, "senate_leadership": s["leadership"] or p.get("senate_leadership", ""), "leadership": "; ".join(([s["leadership"]] if s["leadership"] else []) + lead_bits), "status_note": ""})
        else:
            added.append(s["id"])
            p = {"id": s["id"], "name": s["name"], "kind": "senator", "title": "U.S. Senator", "state": s["state"], "party": s["party"], "since": s["since"], "office_id": s["id"], "committees": codes, "roles": r, "senate_leadership": s["leadership"], "leadership": "; ".join(([s["leadership"]] if s["leadership"] else []) + lead_bits), "priority": 2, "why": "New senator: review priority and record.", "record": "", "status_note": "", "state_assets": [], "state_relevance": 1, "state_why": "", "sources": [BASE + "legislators-current.yaml"], "confidence": "auto"}
            # borrow the state context from a state-mate if we have one
            mate = next((q for q in data["people"] if q.get("kind") == "senator" and q.get("state") == s["state"]), None)
            if mate:
                p["state_assets"], p["state_relevance"], p["state_why"] = mate.get("state_assets", []), mate.get("state_relevance", 1), mate.get("state_why", "")
        people.append(p)
    current = {s["id"] for s in sens}
    for pid, p in old.items():
        if p.get("kind") == "senator" and pid not in current:
            removed.append(pid)
        elif p.get("kind") != "senator":
            # staff: drop only if their office left the Senate
            if p.get("office_id") and p["office_id"].startswith("sen-") and p["office_id"] not in current:
                removed.append(pid)
            else:
                people.append(p)

    data["people"] = people
    data["committee_list"] = clist
    comm_names = {c["code"]: c["name"] for c in clist}
    for c in clist:
        for sc in c["subcommittees"]:
            comm_names[sc["code"]] = c["name"] + " — " + sc["name"]
    comm_names.update({"SSAP-EW": "Appropriations — Energy and Water Development", "SSAS-SF": "Armed Services — Strategic Forces", "SSEV-NUC": "EPW — Clean Air, Climate, and Nuclear Innovation and Safety", "SSEG-EN": "Energy and Natural Resources — Energy"})
    data["committees"] = comm_names
    data["as_of"] = date.today().isoformat()
    data["roster_source"] = "unitedstates/congress-legislators (auto-updated)"
    json.dump(data, open(PEOPLE, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"senators: {len(sens)} (added {len(added)}, kept {len(kept)}, removed {len(removed)}); committees: {len(clist)}; subcommittees: {sum(len(c['subcommittees']) for c in clist)}")
    if added:
        print("added:", ", ".join(added))
    if removed:
        print("removed:", ", ".join(removed))


if __name__ == "__main__":
    main()
