#!/usr/bin/env python3
"""Week 3 · Task 1 — Build your own iterative resolver.

Textbook §2.4.2 - §2.4.3.

This file deliberately sends non-recursive DNS queries and follows every
delegation itself: root -> TLD -> authoritative server.
"""
import argparse
import subprocess
import sys

import dns.exception
import dns.flags
import dns.message
import dns.name
import dns.query
import dns.rcode
import dns.rdatatype


# Root servers. Everything starts here; there is no earlier step.
ROOT_SERVERS = [
    "198.41.0.4",       # a.root-servers.net
    "199.9.14.201",     # b.root-servers.net
    "192.33.4.12",      # c.root-servers.net
]

# (name, kind).  "stable" names must match dig exactly.  "cdn" names are served
# from many replicas and may legitimately give you a different address than dig
# got a second earlier - for those we only require that you reached an answer.
VERIFY_NAMES = [
    ("www.korea.ac.kr", "stable"),
    ("dns.google", "stable"),
    ("en.wikipedia.org", "stable"),
    ("www.stanford.edu", "stable"),
    ("www.microsoft.com", "cdn"),
]


class Resolver:
    """A small iterative (not forwarding) IPv4 DNS resolver."""

    def __init__(self, timeout=2.0, max_depth=30):
        self.timeout = timeout
        self.max_depth = max_depth

    def resolve(self, name):
        """Return ``(IPv4 address, queried-server path)`` for *name*.

        One shared path is passed into nested NS-name and CNAME lookups, so it
        records every server to which this resolver actually sent a packet.
        """
        path = []
        address = self._resolve(name, path, depth=0, resolving=set())
        return address, path

    def _resolve(self, name, path, depth, resolving):
        if depth >= self.max_depth:
            raise RuntimeError("maximum DNS resolution depth exceeded")

        qname = dns.name.from_text(name).canonicalize()
        key = qname.to_text()
        if key in resolving:
            raise RuntimeError(f"DNS dependency loop while resolving {key}")

        resolving.add(key)
        try:
            servers = list(ROOT_SERVERS)

            # Each successful referral consumes one unit of the depth budget.
            for hop in range(depth, self.max_depth):
                response = self._ask_candidates(qname, servers, path)

                # Some authoritative replies include both a CNAME and its A
                # record.  If an A record is present, no new walk is needed.
                for rrset in response.answer:
                    if rrset.rdtype == dns.rdatatype.A:
                        return rrset[0].address

                # A CNAME changes the name.  DNS says to start the search for
                # its target again, which means beginning at a root server.
                for rrset in response.answer:
                    if rrset.rdtype == dns.rdatatype.CNAME:
                        target = rrset[0].target.to_text()
                        return self._resolve(
                            target, path, hop + 1, resolving)

                ns_names = []
                for rrset in response.authority:
                    if rrset.rdtype == dns.rdatatype.NS:
                        ns_names.extend(r.target.canonicalize() for r in rrset)

                if not ns_names:
                    if response.rcode() == dns.rcode.NXDOMAIN:
                        raise LookupError(f"{qname} does not exist")
                    raise LookupError(f"no A answer or delegation for {qname}")

                # Glue is usable only when it belongs to one of the delegated
                # nameservers, not merely because it appears in ADDITIONAL.
                glue = {ns: [] for ns in ns_names}
                for rrset in response.additional:
                    owner = rrset.name.canonicalize()
                    if owner in glue and rrset.rdtype == dns.rdatatype.A:
                        glue[owner].extend(r.address for r in rrset)

                next_servers = []
                for ns_name in ns_names:
                    next_servers.extend(glue[ns_name])

                if not next_servers:
                    # No glue: perform a separate iterative lookup for each NS
                    # name until at least one usable address is found (R3/R4).
                    errors = []
                    for ns_name in ns_names:
                        try:
                            ns_address = self._resolve(
                                ns_name.to_text(), path, hop + 1, resolving)
                            next_servers.append(ns_address)
                        except (LookupError, RuntimeError) as exc:
                            errors.append(str(exc))
                    if not next_servers:
                        detail = "; ".join(errors) or "no nameserver addresses"
                        raise LookupError(f"could not resolve delegation: {detail}")

                # Preserve server order while removing duplicate glue records.
                servers = list(dict.fromkeys(next_servers))

            raise RuntimeError("maximum DNS resolution depth exceeded")
        finally:
            resolving.remove(key)

    def _ask_candidates(self, qname, servers, path):
        """Ask candidates in order, skipping timeouts and broken servers."""
        last_error = None
        for server in servers:
            path.append(server)
            query = dns.message.make_query(qname, dns.rdatatype.A)
            query.flags &= ~dns.flags.RD       # recursion desired = false (R2)
            try:
                response = dns.query.udp(query, server, timeout=self.timeout)
                if response.flags & dns.flags.TC:
                    response = dns.query.tcp(query, server, timeout=self.timeout)
                if response.rcode() in (dns.rcode.NOERROR, dns.rcode.NXDOMAIN):
                    return response
                last_error = RuntimeError(
                    f"{server} returned {dns.rcode.to_text(response.rcode())}")
            except (dns.exception.DNSException, OSError) as exc:
                last_error = exc

        raise LookupError(
            f"none of the candidate DNS servers answered: {last_error}")


# ------------------------------------------------------------------- harness
def dig_answer(name):
    """What the system resolver says, for comparison."""
    out = subprocess.run(["dig", "+short", name, "A"],
                         capture_output=True, text=True).stdout
    return [line for line in out.split() if line and line[0].isdigit()]


def verify():
    r, failures = Resolver(), 0
    for name, kind in VERIFY_NAMES:
        try:
            addr, path = r.resolve(name)
        except NotImplementedError:
            print("Nothing implemented yet - write Resolver.resolve first.")
            return 1
        except Exception as e:
            print(f"  FAIL  {name:<22} your resolver raised {e!r}")
            failures += 1
            continue
        expected = dig_answer(name)
        if addr in expected:
            note = ""
        elif kind == "cdn":
            note = "  <- differs, but this name is CDN-hosted. Explain it."
        else:
            note = "  <- should have matched"
            failures += 1
        print(f"  {'FAIL' if note.endswith('matched') else 'ok  '}  {name:<22} "
              f"you={addr:<16} dig={','.join(expected) or '-'}   "
              f"hops={len(path)}{note}")
    print(f"\n  {len(VERIFY_NAMES) - failures}/{len(VERIFY_NAMES)} ok")
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name", nargs="?", default="www.korea.ac.kr")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.verify:
        sys.exit(verify())

    addr, path = Resolver().resolve(args.name)
    for i, server in enumerate(path, 1):
        print(f"  {i}. asked {server}")
    print(f"\n  {args.name} -> {addr}")


if __name__ == "__main__":
    main()
