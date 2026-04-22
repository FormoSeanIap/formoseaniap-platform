# Backlog

Curated follow-up work for the portfolio platform.

## Now

- _None_

## Next

## Later

- [ ] Recalibrate the analytics cost estimate in `README.md` against the post-Lane-C write pattern
  - Why: Lane C dropped the third `SITE#ALL` write per collect event, which both made the README's "two uniqueness writes and performs two counter updates" description accurate and shifted the actual DynamoDB cost per 1M requests downward by roughly a third. The "Cost Estimate" dollar figures were order-of-magnitude placeholders that predate Lane C and have not been recomputed.
  - Scope: compute the real DynamoDB on-demand cost per 1M collect events under the new 2 unique-claim + 2 counter-update pattern at Free-tier pricing, update the per-1M-request line, and propagate into the Small/Medium/Large scenario rows.
  - Done when: the cost table in `README.md` reflects the post-Lane-C write count, and the backend variable cost line in the Variable backend cost section is consistent with it.

- [ ] Complete the `formoseaniap.com` cutover while Cloudflare remains authoritative
  - Why: the infrastructure now supports the branded production hostname, but Cloudflare must stay as the live DNS provider until the new-domain transfer lock expires.
  - Scope: run a plain `terraform apply`, create the ACM validation records manually in Cloudflare from the Terraform manual-DNS outputs if the first apply stops at validation, rerun the same plain apply, then add the final cutover records in Cloudflare, verifying `www` as the canonical host plus apex and legacy CloudFront redirects.
  - Done when: `https://www.formoseaniap.com` is the canonical public site, `https://formoseaniap.com` and the old CloudFront hostname redirect there, and the dedicated analytics auth subdomain is serving Cognito managed login while Cloudflare remains the live DNS authority.

- [ ] Transfer `formoseaniap.com` DNS authority to Route 53 and then enable DNSSEC
  - Why: the current Cloudflare-authoritative setup requires manual DNS mirroring; after the transfer hold expires, Route 53 should become the single source of truth and DNSSEC can be enabled there cleanly.
  - Scope: once the registrar lock window allows it (probably 6/13, from 4/14 + 60 days), move nameserver control or the registrar itself so Route 53 becomes authoritative, remove the need to mirror records into Cloudflare, then design and implement DNSSEC as a follow-up in the now-authoritative Route 53 setup.
  - Done when: Route 53 is authoritative for `formoseaniap.com`, the live DNS records are served directly from the Terraform-managed hosted zone, and DNSSEC validates publicly without depending on manual Cloudflare DNS mirroring.
