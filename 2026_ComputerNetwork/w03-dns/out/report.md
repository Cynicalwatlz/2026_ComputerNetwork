# DNS Steering Report

## Measurements

Networks compared: `hotspot`, `wifi`.
Resolvers compared on each network: `system`, `google`, and `quad9`.

## CNAME and third-party classification

Simple rule: take the last two DNS labels as the organizational domain. If the original site's organizational domain differs from the final CNAME's organizational domain, classify it as third-party.

| site | chain length | final zone | third party? | rule verdict |
|---|---:|---|---|---|
| www.microsoft.com | 2 | akamaiedge.net | yes | yes — correct |
| www.netflix.com | 1 | netflix.com | no | no — correct |
| www.adobe.com | 2 | akamai.net | yes | yes — correct |
| www.cnn.com | 1 | fastly.net | yes | yes — correct |
| www.apple.com | 3 | akamaiedge.net | yes | yes — correct |
| www.korea.ac.kr | 0 | ac.kr | no | no — correct |
| www.stanford.edu | 1 | netlifyglobalcdn.com | yes | yes — correct |
| www.bbc.co.uk | 2 | fastly.net | yes | yes — correct |
| www.spotify.com | 1 | fastly.net | yes | yes — correct |
| www.github.com | 1 | github.com | uncertain | no — inconclusive (CNAME evidence alone) |
| www.wikipedia.org | 1 | wikimedia.org | no | yes — wrong |
| www.nytimes.com | 3 | fastly.net | yes | yes — correct |

Chain length is the number of CNAME hops, so a site with no CNAME has length 0. The `third party?` column is the defended classification; the final column shows the simple rule's answer and whether it agrees.

### Known rule failure and ambiguity

The rule misclassifies Wikipedia: `www.wikipedia.org` points to `dyna.wikimedia.org`. Comparing `wikipedia.org` with `wikimedia.org` produces a third-party verdict, but Wikimedia operates Wikipedia, so this is an affiliated/own delivery name rather than a third-party CDN.

GitHub ends at `github.com`, so the simple rule says not third-party. However, a CNAME chain alone cannot establish whether GitHub is CDN-hosted or whether delivery is an own versus third-party service; it is therefore marked inconclusive and excluded from the CDN steering denominator.

Korea University is treated as no CDN for this analysis. Netflix is CDN-hosted but uses its own `netflix.com` naming, illustrating why third-party and CDN-hosted are not the same classification.

## Steering result

**7 of 10 CDN-hosted sites answered differently to a different resolver or network.**

Sites with differing address sets: www.microsoft.com, www.adobe.com, www.cnn.com, www.apple.com, www.bbc.co.uk, www.spotify.com, www.nytimes.com.

This value is computed from `chains.json`: for each of the ten designated CDN-hosted sites, the code compares address sets across all resolvers and both recorded networks. Set comparison ignores address ordering.

## Part A: iterative DNS trace

- Delegation response: packet 2
- Final answer response: packet 6
- Largest DNS response: 383 bytes
- Observation: the largest response was large because it contained multiple NS delegation records and 10 additional records.
