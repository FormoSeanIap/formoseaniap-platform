---
id: technical-devops-sre-diaries-building-a-reliable-maintenance-mode-part-4-challenges-behind-the-tool
lang: en
title: "Challenges During Development"
slug: challenges-behind-the-tool
excerpt: "The engineering detours behind the new tool, from legacy DNS confusion to WAF state tokens and CLB-to-ALB migration surprises."
category: technical
tags:
  - technical
  - operation-diaries
  - sre
  - aws
  - dns
  - maintenance-mode
published_at: 2026-03-24
updated_at: 
read_time: 5
external_url: 
cover_image: 
draft: false
series_id: technical-devops-sre-diaries-building-a-reliable-maintenance-mode
series_title: "Building A Reliable Maintenance Mode"
part_number: 4
---

![source: https://www.freepik.com/free-vector/construction-landing-page_4455395.htm#fromView=search&page=1&position=0&uuid=5ed236a5-e6f6-4dd8-8889-cdb1e118547a&query=maintenance+mode](./Figure1.png "source: [Freepik](https://www.freepik.com/free-vector/construction-landing-page_4455395.htm#fromView=search&page=1&position=0&uuid=5ed236a5-e6f6-4dd8-8889-cdb1e118547a&query=maintenance+mode)")

In [the previous article](../Part3/The_New_Tool.md), we walked through the new maintenance mode tool:
how we simplified the architecture, introduced AWS WAF, and reduced the operational complexity that plagued the legacy system.

Now that the architecture looks neat on paper, it’s easy to forget that getting there was anything but straightforward.

In this article, I want to step away from diagrams and happy paths, and talk about something equally important:
- the real challenges we faced while building the tool,
- the hidden complexity buried in legacy systems, and
- the technical detours that shaped the final design.

If the earlier articles focused on what we built, this one is about how hard it was to build it—and why that process matters.

Although the high-level design of the maintenance mode tool looks quite clean now, the actual development process was anything but straightforward.

Looking back, the main difficulties can be grouped into three areas:
1.	The complexity and historical baggage of the original architecture
2.	The WAF API design and its state-management model
3.	The migration from Classic Load Balancer (CLB) to Application Load Balancer (ALB) and the unexpected issues that came with it

Let’s go through them one by one.

## Getting Lost in Legacy DNS and Routing

The first major challenge was simply understanding the existing architecture.

On paper, the DNS records looked “okay.”

In reality, the routing behavior was confusing and full of historical baggage.

Some DNS routing rules were so unintuitive that I literally spent a full week “lost” in them.
It wasn’t until a senior engineer walked me through the history behind those records that I realized what was going on:

Hidden “side paths” in DNS, created long ago for specific reasons, then forgotten—
but still affecting how traffic flowed.

This experience was a reminder that legacy systems are not just code and resources.
They’re also made of past decisions, temporary workarounds, and undocumented assumptions that new engineers must slowly uncover.

## Wrestling with the WAF API and State Tokens

The second major difficulty lay in the implementation of the maintenance mode tool itself.

I essentially wrote a brand-new tool from scratch.
Starting from zero is already time-consuming, but the longest “stuck period” was around the WAF API design.

In AWS WAF, resources are managed using a kind of state token
(if you’re familiar with Terraform, it’s a bit like working with a state file):
- Every time you modify a WAF resource,
- you must first have the latest token returned from the previous update,
- and then include that token in the next request.

Without the correct token, the update simply fails.

This meant that for every single change, the tool had to:
1.	Retrieve the current state and token
2.	Apply the modification
3.	Store the new token to be used for the next operation

On top of that, creating each WAF Web ACL takes a noticeable amount of time.
Because of this, after creating a Web ACL, I had to insert an additional step in the script:

A loop that repeatedly checks whether the Web ACL is ready
before proceeding to create the associated Rules and attach it to the ALB.

At first, my implementation followed this pattern:
1.	Create a Web ACL
2.	Wait for it to become available
3.	Create its Rules
4.	Attach it to the ALB
5.	Repeat the whole process for the next Web ACL

However, each maintenance operation required multiple Web ACLs.
Because the creation was strictly sequential, we had to wait for each ACL to be ready before moving on.

The result?

It could easily take more than ten minutes just to get into maintenance mode.

In the end, I had to redesign the logic:
- First, create all the required Web ACLs in advance
- Then, once they are all ready, proceed to create the corresponding Rules and ALB attachments
This change sounds small, but it drastically reduced the overall time needed to enter maintenance mode and made the tool much more usable in real operations.

## Migrating from CLB to ALB (and Falling into an HTTP Version Trap)

The third challenge was load balancer migration.

Some of our services were still using the older AWS Classic Load Balancer (CLB).
However, CLB cannot be integrated with WAF.
So during the development of the maintenance mode tool, I had to migrate those services from CLB to ALB.

From an architectural perspective, this was a major project on its own:
- We had to create new ALBs and all related resources
- There were many AWS-specific configuration details that were easy to overlook
- We also had to carefully adjust Route 53 settings to cut over traffic safely
- At the same time, we needed to keep our existing infrastructure and configuration management tools
(in our case, AWS CloudFormation and AWS OpsWorks) in sync,
to avoid breaking future deployments

Even after the migration was “completed,” a new, unexpected problem appeared:
•	ALB, by default, uses HTTP/2 or higher
•	Our existing clients that previously connected to CLB were still using HTTP/1.1

This mismatch caused behavior we did not initially expect.

To quickly stabilize the system, we temporarily disabled HTTP/2 on the ALB, forcing it to behave more like the original CLB from the clients’ perspective.

Only after that did things return to normal.

This was a good reminder that:

Infrastructure changes often have protocol-level side effects, not just resource-level ones.
Knowledge Supplement
- AWS Classic Load Balancer (CLB):
An older load balancing service from AWS that has largely been superseded by newer options.
In our case, we migrated from CLB to ALB to support WAF integration.
- AWS CloudFormation (CloudFormation):
One of AWS’s native Infrastructure as Code (IaC) tools,
used to define and manage infrastructure using templates.
- AWS OpsWorks (OpsWorks):
AWS’s native configuration management and automation service, based on Chef and Puppet.
Similar tools include Ansible.
- HTTP/1.1 vs HTTP/2:
Different protocol versions of HTTP.
HTTP/2 addresses and improves many limitations of HTTP/1.1, such as head-of-line blocking and connection usage.

# Conclusion

In this article, we looked at what it really took to bring the new maintenance mode tool to life:
- untangling confusing legacy DNS and routing,
- wrestling with WAF’s stateful API and long-lived operations, and
- navigating a CLB-to-ALB migration that surfaced unexpected HTTP-version issues.

These stories rarely show up in architecture diagrams, but they are where most of the real engineering effort goes.

In the next—and final—article, we’ll shift from “how we fixed things” to “where we’re going next”:
- how we plan to evolve the tool beyond a local script,
- how Slack, Lambda, and Google Sheets could turn it into an event-driven workflow, and
- what this entire journey taught me about the mindset an SRE should cultivate.

Read [the next article](../Part5/Future_Directions_and_SRE_Reflections.md).
