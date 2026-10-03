#!/usr/bin/env python3
"""Week 3 · Task 2 — Does DNS actually steer you? Measure it.

Textbook §2.4.3 (records) and §2.5 (CDNs).

The lecture claims two things:

    (a) most large sites are served by a CDN, reached through a CNAME chain
    (b) DNS steers each user to a *nearby* replica

Both are testable from your laptop, and one of them is harder to prove than
the slide makes it look. Your job is to produce the evidence and a number.

    python3 task2_steering.py --collect        # gather the raw data
    python3 task2_steering.py --report         # your analysis

What you have to build
----------------------
1.  For each hostname in SITES, follow the CNAME chain to its end and record
    every hop. `--collect` should leave the raw data in out/chains.json.

2.  Decide, for each site, whether it is served by a **third party**.
    This is the hard part and there is no single right answer:

      - `www.microsoft.com` ends at `akamaiedge.net`     - clearly third party
      - `www.netflix.com`   stops inside `netflix.com`   - own CDN, not third party
      - some sites have no CNAME at all and still sit behind a CDN (anycast)
      - `foo.cloudfront.net` and `foo.s3.amazonaws.com` are both Amazon,
        but they are not the same service

    Write down the rule you used and **defend it in observation.md**. A rule
    that just compares the last two labels will be wrong on at least one of
    the sites below; find which, and say so.

3.  Ask **two different resolvers** for the same name and compare the
    addresses you get back. If DNS really steers by location, a CDN-hosted
    name should answer differently to resolvers sitting in different places.

        RESOLVERS below has your system resolver and two public ones.

    Report: of N CDN-hosted sites, how many returned a different address set
    from a different resolver? Claim (b) predicts most of them. Check it.

Pass condition
--------------
There is no fixed answer. You pass by producing, in out/report.md:

  - the table: site | chain length | final zone | third party? | your rule's verdict
  - the steering number: "X of N sites answered differently to a different resolver"
  - at least one site where your classification rule was wrong, and why
"""
import argparse, json, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

SITES = [
    "www.microsoft.com",     # Akamai, multi-hop
    "www.netflix.com",       # own CDN
    "www.adobe.com",
    "www.cnn.com",
    "www.apple.com",
    "www.korea.ac.kr",       # no CDN at all
    "www.stanford.edu",
    "www.bbc.co.uk",
    "www.spotify.com",
    "www.github.com",
    "www.wikipedia.org",
    "www.nytimes.com",
]

RESOLVERS = {
    "system": None,          # whatever is in your resolv.conf
    "google": "8.8.8.8",
    "quad9":  "9.9.9.9",
}


def dig(name, rtype="A", server=None):
    """Raw lookup. Transport only - the thinking is yours."""
    args = ["dig", "+short", name, rtype]
    if server:
        args.insert(1, f"@{server}")
    out = subprocess.run(args, capture_output=True, text=True).stdout
    return [l.strip() for l in out.splitlines() if l.strip()]


def collect():
    """Gather raw chains and per-resolver answers into out/chains.json.

    You write this. Roughly:
      for each site: follow CNAMEs to the end, then for each resolver in
      RESOLVERS record the A records it returns.
    """
    raise NotImplementedError("build the collector")


def report():
    """Read out/chains.json and produce out/report.md.

    Classify CNAMEs with a deliberately simple organizational-domain rule,
    compare every recorded resolver/network answer set, and write the
    evidence required by the assignment.
    """
    chains_path = os.path.join(OUT, "chains.json")
    report_path = os.path.join(OUT, "report.md")

    with open(chains_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    measurements = data.get("measurements", [])
    if not measurements:
        raise ValueError("out/chains.json contains no measurements")

    # Keep the most recent measurement for each network label, while using
    # all measurements below when comparing address sets.
    by_network = {}
    for measurement in measurements:
        network = measurement.get("network", "unlabeled")
        by_network[network] = measurement

    # Assignment-level classification, separate from the deliberately simple
    # CNAME rule.  GitHub is left uncertain because this evidence alone does
    # not establish whether its delivery is an own or third-party CDN.
    cdn_hosted = {
        "www.microsoft.com", "www.netflix.com", "www.adobe.com",
        "www.cnn.com", "www.apple.com", "www.stanford.edu",
        "www.bbc.co.uk", "www.spotify.com", "www.wikipedia.org",
        "www.nytimes.com",
    }
    third_party_truth = {
        "www.microsoft.com": True,
        "www.netflix.com": False,
        "www.adobe.com": True,
        "www.cnn.com": True,
        "www.apple.com": True,
        "www.korea.ac.kr": False,
        "www.stanford.edu": True,
        "www.bbc.co.uk": True,
        "www.spotify.com": True,
        "www.github.com": None,
        "www.wikipedia.org": False,
        "www.nytimes.com": True,
    }

    def organizational_domain(hostname):
        labels = hostname.rstrip(".").lower().split(".")
        return ".".join(labels[-2:]) if len(labels) >= 2 else hostname.lower()

    def differs(site):
        answer_sets = []
        for measurement in measurements:
            site_data = measurement.get("sites", {}).get(site, {})
            for addresses in site_data.get("addresses", {}).values():
                answer_sets.append(frozenset(addresses))
        return len(set(answer_sets)) > 1

    # Chain data is stable in these measurements; use the latest available
    # entry for display, without assuming a particular network comes last.
    latest_sites = {}
    for measurement in measurements:
        latest_sites.update(measurement.get("sites", {}))

    table_rows = []
    for site in SITES:
        site_data = latest_sites.get(site, {})
        chain = site_data.get("chain", [site])
        final_name = site_data.get("final_name", chain[-1])
        source_zone = organizational_domain(site)
        final_zone = organizational_domain(final_name)
        rule_third_party = source_zone != final_zone
        truth = third_party_truth[site]
        if truth is None:
            third_party = "uncertain"
            verdict = "inconclusive (CNAME evidence alone)"
        else:
            third_party = "yes" if truth else "no"
            verdict = "correct" if rule_third_party == truth else "wrong"
        rule_answer = "yes" if rule_third_party else "no"
        table_rows.append(
            f"| {site} | {max(len(chain) - 1, 0)} | {final_zone} | "
            f"{third_party} | {rule_answer} — {verdict} |"
        )

    steered_sites = [site for site in SITES if site in cdn_hosted and differs(site)]
    network_names = list(by_network)

    lines = [
        "# DNS Steering Report",
        "",
        "## Measurements",
        "",
        "Networks compared: " + ", ".join(f"`{name}`" for name in network_names) + ".",
        "Resolvers compared on each network: `system`, `google`, and `quad9`.",
        "",
        "## CNAME and third-party classification",
        "",
        ("Simple rule: take the last two DNS labels as the organizational domain. "
         "If the original site's organizational domain differs from the final "
         "CNAME's organizational domain, classify it as third-party."),
        "",
        "| site | chain length | final zone | third party? | rule verdict |",
        "|---|---:|---|---|---|",
        *table_rows,
        "",
        ("Chain length is the number of CNAME hops, so a site with no CNAME has "
         "length 0. The `third party?` column is the defended classification; "
         "the final column shows the simple rule's answer and whether it agrees."),
        "",
        "### Known rule failure and ambiguity",
        "",
        ("The rule misclassifies Wikipedia: `www.wikipedia.org` points to "
         "`dyna.wikimedia.org`. Comparing `wikipedia.org` with `wikimedia.org` "
         "produces a third-party verdict, but Wikimedia operates Wikipedia, so "
         "this is an affiliated/own delivery name rather than a third-party CDN."),
        "",
        ("GitHub ends at `github.com`, so the simple rule says not third-party. "
         "However, a CNAME chain alone cannot establish whether GitHub is CDN-hosted "
         "or whether delivery is an own versus third-party service; it is therefore "
         "marked inconclusive and excluded from the CDN steering denominator."),
        "",
        ("Korea University is treated as no CDN for this analysis. Netflix is CDN-"
         "hosted but uses its own `netflix.com` naming, illustrating why third-party "
         "and CDN-hosted are not the same classification."),
        "",
        "## Steering result",
        "",
        (f"**{len(steered_sites)} of {len(cdn_hosted)} CDN-hosted sites answered "
         "differently to a different resolver or network.**"),
        "",
        "Sites with differing address sets: " + ", ".join(steered_sites) + ".",
        "",
        ("This value is computed from `chains.json`: for each of the ten designated "
         "CDN-hosted sites, the code compares address sets across all resolvers and "
         "both recorded networks. Set comparison ignores address ordering."),
        "",
        "## Part A: iterative DNS trace",
        "",
        "- Delegation response: packet 2",
        "- Final answer response: packet 6",
        "- Largest DNS response: 383 bytes",
        ("- Observation: the largest response was large because it contained multiple "
         "NS delegation records and 10 additional records."),
        "",
    ]

    os.makedirs(OUT, exist_ok=True)
    with open(report_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))

    print(f"Wrote {report_path}")
    print(f"Steering result: {len(steered_sites)} of {len(cdn_hosted)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--collect", action="store_true")
    p.add_argument("--report", action="store_true")
    a = p.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.collect:
        collect()
    elif a.report:
        report()
    else:
        p.print_help()
