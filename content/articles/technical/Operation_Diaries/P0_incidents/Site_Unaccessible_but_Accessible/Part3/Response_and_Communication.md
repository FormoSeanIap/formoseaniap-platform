---
id: technical-devops-sre-diaries-p0-incidents-site-unaccessible-but-accessible-part-3-response-and-communication
lang: en
title: "Response and Communication"
slug: response-and-communication
excerpt: "How the team handled the NS rollback, customer communication, and propagation risk after a confusing DNS outage."
category: technical
tags:
  - technical
  - sre
  - incident
  - dns
  - operations
  - system-outages
published_at: 2026-03-24
updated_at: 
read_time: 2
external_url: 
cover_image: 
draft: false
series_id: technical-devops-sre-diaries-p0-incidents-site-unaccessible-but-accessible
series_title: "Site Unaccessible but Accessible"
part_number: 3
---

![Figure 1: Website Down Alert](./Figure1.jpg "Source: [Freepik](https://www.freepik.com/free-vector/gradient-pop-up-set-with-different-purposes_18990425.htm#fromView=keyword&page=1&position=2&uuid=d6b2a079-5764-4675-8ccd-3f987c411419&query=Website+down)")

[Part 2: DNS Background and Root Cause](../Part2/DNS_Background_and_Root_Cause.md)

# Initial Response

Once we understood what happened, the fix sounded simple: ask the customer to change the NS record back.
But the first question was: why did the customer change it in the first place?

In practice, we had to confirm whether the customer truly made the change.
Technically we could infer it, but verifying it without sounding accusatory took time.
This was mainly the product manager's work rather than SRE.

We eventually learned the reason: they wanted to change some DNS routing rules and add a new domain.
The correct process would have been to send us the requested changes so we could apply them at the right time.

Due to communication or handoff issues, they instead changed the NS record and updated DNS settings on their own platform.
That platform was separate from ours, which meant our existing routing rules were no longer in effect.

# Communication Challenges

The second major problem was communication.
The customer was a Japanese company.
As mentioned in the earlier article on alerting, we typically rely on a Japanese-speaking product manager during incidents.

In some complex situations we must bypass the product manager and communicate directly with the customer.
This incident qualified because:
- It was a P0 emergency.
- The situation was too complex to translate accurately.
- The required changes had to be performed by the customer.

We ended up talking directly with the customer's product manager rather than their engineers, since their engineers did not speak English.

During the discussion, the customer could not understand why we asked them to change NS records.
They repeatedly requested assurance that the change would not overwrite their intended DNS updates.
From their perspective, that concern was valid: reverting the NS record would indeed remove their new DNS settings.

From our side, we could not be 100% certain that the change would restore service immediately, especially as user reports of inaccessibility started arriving (DNS propagation was already in progress).
Explaining this in English while the DNS cache delays were still in play was highly stressful.

# Short-Term Fix and Follow-Up

Fortunately, after the NS record was reverted, we quickly received Pingdom UP alerts.
That confirmed the primary outage was resolved.

However, I must admit a mistake: after restoring the NS record, I did not immediately apply the DNS changes the customer originally wanted.
As a result, some services remained broken, and access varied by device due to DNS propagation.

Only later that evening, after I fully understood the DNS configuration and applied the customer's intended changes, was the issue completely resolved.

# Next

In Part 4, I will share the DNS tools and commands that were essential during this incident, along with final reflections.

[Continue to Part 4](../Part4/Tools_and_Reflections.md)
