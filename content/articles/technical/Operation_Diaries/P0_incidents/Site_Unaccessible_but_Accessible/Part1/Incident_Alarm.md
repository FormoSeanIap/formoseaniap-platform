---
id: technical-devops-sre-diaries-p0-incidents-site-unaccessible-but-accessible-part-1-incident-alarm
lang: en
title: "Incident Alarm"
slug: incident-alarm
excerpt: "A P0 incident story that begins with every Pingdom node reporting downtime while the site still appears reachable from the team side."
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
part_number: 1
---

![Figure 1: Website Down Alert](./Figure1.jpg "Source: [Freepik](https://www.freepik.com/free-vector/gradient-pop-up-set-with-different-purposes_18990425.htm#fromView=keyword&page=1&position=2&uuid=d6b2a079-5764-4675-8ccd-3f987c411419&query=Website+down)")

## About This Series

This is the first article in a four-part series about a perplexing P0 incident where monitoring systems reported a full outage, yet the site appeared accessible.  
We will explore the investigation process, the DNS mechanics behind the issue, the challenges in response and communication, and the tools and lessons learned.

### Series Outline:
1. **Incident Alarm** (this article)
2. **DNS Background and Root Cause**
3. **Response and Communication**
4. **Tools and Reflections**


## Incident Overview

The incident began with a series of Pingdom DOWN alerts, signaling a potential full outage.

### What is a Pingdom DOWN Alert?

Pingdom is a popular monitoring tool that ensures the availability and performance of websites and services.  
It simulates user interactions from various global locations, checking if the service responds as expected. If the service fails to respond or returns an error, Pingdom triggers an alert.

### Why Use Pingdom?

Pingdom's distributed checks are invaluable for detecting issues that internal monitoring might miss.  
For instance, a DNS misconfiguration affecting specific regions can be caught by Pingdom, even if internal systems show the site as functional.

However, this distributed nature can sometimes lead to confusion.  
If only certain Pingdom nodes report failures, it might indicate a regional or transient issue.  
In this case, though, every Pingdom node reported the site as down, making the situation even more puzzling.

Pingdom doesn't just check if the site is reachable; it verifies specific criteria like HTTP status codes, response times, and content matching.  
This ensures the service is not only up but functioning correctly.

In this incident, Pingdom's alerts were accurate and highlighted a deeper issue that internal monitoring missed.  
This underscores the importance of external monitoring tools like Pingdom, even if they occasionally raise questions requiring further investigation.

## The Alert

At the time, every Pingdom alert for this project fired simultaneously, indicating a full site-down event.  
Yet, when I accessed the site directly, it loaded normally. The verification team also confirmed the system was reachable.

Pause for a moment and consider: What could cause this discrepancy? How would you investigate?

Initially, I suspected a false alarm or a Pingdom misjudgment.  
If it were that simple, this incident wouldn't be worth documenting.

At the time, I was completely baffled.  
I reviewed Pingdom's response details, but nothing stood out.  
Since the site was accessible, I was tempted to blame Pingdom itself.

The breakthrough came when a senior engineer shared DNS query results showing that the service's Name Server had been replaced.  
This revelation turned confusion into a concrete lead.

---

## Next Steps

In Part 2, we will dive into DNS fundamentals and explain how a Name Server change can trigger this type of alert.

[Continue to Part 2](../Part2/DNS_Background_and_Root_Cause.md)
