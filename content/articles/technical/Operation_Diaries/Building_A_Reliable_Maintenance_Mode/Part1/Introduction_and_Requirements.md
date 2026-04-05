---
id: technical-devops-sre-diaries-building-a-reliable-maintenance-mode-part-1-introduction-and-requirements
lang: en
title: "About This Series"
slug: introduction-and-requirements
excerpt: "An introduction to why maintenance mode matters in production systems and the operational requirements behind a reliable maintenance workflow."
category: technical
tags:
  - technical
  - operation-diaries
  - sre
  - maintenance-mode
  - operations
published_at: 2026-03-24
updated_at: 
read_time: 4
external_url: 
cover_image: 
draft: false
series_id: technical-devops-sre-diaries-building-a-reliable-maintenance-mode
series_title: "Building A Reliable Maintenance Mode"
part_number: 1
---

![Figure 1: Maintenance Mode](./Figure1.png "Source: [Freepik](https://www.freepik.com/search?format=search&last_filter=query&last_value=maintenance+mode&query=maintenance+mode)")

This article is the first in a five-part series that walks through how our team designed, implemented, and continuously improved a practical maintenance mode system.

The goal is not only to explain the technical solution, but also to uncover the real-world decision-making, challenges, and lessons learned along the way—from architecture design to tooling evolution and long-term operational thinking.

The series is structured as follows:

1. **Introduction** – Why maintenance mode is necessary, what it means in practice, and the key requirements for building such a system. (← this article)
2. **The Old System** – How maintenance mode was originally implemented, including its strengths, limitations, and operational challenges.
3. **The New System** – The redesigned solution using AWS WAF, and how it simplified architecture, improved usability, and solved previous pain points.
4. **Challenges During Development** – The behind-the-scenes engineering challenges, including legacy DNS issues, WAF API design, and CLB-to-ALB migration.
5. **Future Directions & Reflections** – How the tool could evolve into a more automated, event-driven system (Lambda, Slack, API integration), and what this journey teaches about the SRE mindset.

By the end of this series, you will have a full picture of how a maintenance mode system evolves—from initial concept, through real-world engineering challenges, to future-ready operational design.

# Introduction

When a system is officially launched after development, the work is far from over.
In fact, maintaining and improving a system is a continuous process.
New versions are released regularly, and even when there are no new features, the underlying resources and dependencies still require maintenance.
For example, security patches, operating system updates, and infrastructure upgrades are inevitable over time.

Ideally, these updates would be invisible to users and have no effect on service availability.
However, in practice, it is sometimes necessary to accept a certain amount of downtime in exchange for safer, more reliable deployment methods.
This trade-off is not just a technical decision but also a risk-management strategy.
In the project I was responsible for, we adopted this very principle.

To ensure that users are not confused or misled when the system is temporarily unavailable, and to make sure they clearly understand that the downtime is intentional and temporary, we introduce what is called “maintenance mode.”
When activated, this mode informs users that the system is under maintenance and cannot be accessed.

At one of my former companies, enabling maintenance mode is part of the Site Reliability Engineering (SRE) team’s responsibilities.
Given the size and complexity of our system, switching between maintenance mode and normal operation must be done in a way that is not only efficient but also easy to manage.
Designing a proper solution to achieve this balance became one of the key goals of our project.

# Maintenance Mode Requirements

Maintenance mode can generally be divided into three stages:
1.	Initial Entry into Maintenance Mode
Once maintenance mode is activated, anyone accessing the website will see a dedicated maintenance page.
At the same time, all direct API calls will return an HTTP Status Code 503, indicating that the service is temporarily unavailable.
2.	Testing Phase with Whitelisting
After new features have been deployed, certain users—such as QA engineers or other testers—need access in order to verify the system’s behavior.
This is achieved through a whitelist mechanism, which allows only authorized testers to bypass the maintenance page.
Regular users, however, will still encounter the maintenance screen.
3.	Exiting Maintenance Mode
Once all testing and final checks are complete, the system exits maintenance mode and resumes normal operation.
At this point, every user should once again be able to access the website and its services without restriction.

Based on these requirements, the tool we designed must provide the following four key functions:
•	Enter maintenance mode
•	Exit maintenance mode
•	Enable a whitelist while in maintenance mode
•	Disable the whitelist while in maintenance mode

Although the fourth function (disabling the whitelist) may not be frequently used, it was still included in the design.
This is because in real-world scenarios, testing sometimes reveals issues that require redeployment.
Having the ability to turn off whitelisting without leaving maintenance mode provides greater flexibility and avoids unnecessary complexity during troubleshooting.

# Conclusion

In this article, we introduced the idea of maintenance mode—why it is necessary, how it works in principle, and the key requirements for building a reliable solution.
We also explained the three main stages of maintenance mode and the essential functions that support them.

In [the next article](../Part2/The_Legacy_System.md), we will take a closer look at the old maintenance mode system that our company originally used.
We will examine its properties, how it was implemented, and the challenges that arose in day-to-day operations.
Understanding the limitations of the old system is crucial, because it helps explain why we needed to design a new approach in the first place.

# Knowledge Corner

•	API (Application Programming Interface): A way for applications to communicate and integrate with each other. In this case, even if the frontend shows a maintenance message, malicious actors could still directly call backend APIs if they were not blocked. If those API calls modified database records, it could lead to unexpected or harmful results.
•	HTTP Status Code 503: Indicates that the server is unavailable, typically due to overload or planned maintenance.
•	QA (Quality Assurance): The process of verifying that a product meets expected quality standards, ensuring functionality, stability, and reliability through systematic testing.
