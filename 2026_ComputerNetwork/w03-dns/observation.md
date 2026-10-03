# Task 1 observations

The root server did not return the final address because it stores delegations for top-level domains, not every host record; it directed the resolver to the next DNS layer instead. When a referral had no glue A record, the resolver started a separate root-to-authoritative lookup for the nameserver's hostname, then returned to the original lookup; every server contacted by that extra walk is included in `path`.

The exact hop count is shown by `python3 task1_resolve.py <name>` (and summarized by `--verify`) and can vary when a server times out or a no-glue lookup is needed. This is several authoritative-server queries, whereas a laptop normally sends one recursive query to its configured resolver and lets that resolver perform or cache the walk; CDN answers may differ because separate queries can be routed to different replicas.
