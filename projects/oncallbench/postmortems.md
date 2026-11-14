# Postmortems behind the levers

Read on 14 Nov 2026 for round 4 of the loop (`LOOP.md`). Each entry: what happened, what misled the
responders, which mitigation helped or backfired, and the lever it suggests for the environment.
Times are as the source gives them. Quotes are from the linked source.

## Cloudflare, 18 November 2025: a feature file that doubled

Source: [Cloudflare outage on November 18, 2025](https://blog.cloudflare.com/18-november-2025-outage/).

- **What happened.** A ClickHouse permissions change at 11:05 UTC made a metadata query return
  duplicate rows, so the Bot Management feature file "doubled in size" and was pushed to every
  machine. The proxy preallocates room for 200 features; the file went over and the proxy panicked,
  returning 5xx ([source](https://blog.cloudflare.com/18-november-2025-outage/)).
- **What misled them.**
  - The failure came and went: the file was "generated every five minutes" and "bad data was only
    generated if the query ran on a part of the cluster which had been updated", so "the entire
    system would recover and then fail again". "This was very unusual behavior for an internal
    error."
  - "We initially wrongly suspected the symptoms we were seeing were caused by a hyper-scale DDoS
    attack."
  - The status page, hosted off Cloudflare, went down at the same time: "it turned out to be a
    coincidence", but it led some to think "an attacker may be targeting both our systems as well
    as our status page".
  - From 11:32 to 13:05 the visible symptom was Workers KV, a victim, and the first mitigations
    ("traffic manipulation and account limiting") went there.
- **Mitigations.**
  - Helped partly: bypassing the proxy for Workers KV and Access at 13:05 ("impact reduced").
  - Fixed it: at 14:24 they "stopped creation and propagation of new Bot Management configuration
    files", then inserted "a known good file into the feature file distribution queue" and forced
    a restart of the proxy. Undoing the trigger alone would not have removed the file already on
    every machine.
  - Recovery had its own outage: "A backlog of login attempts began to overwhelm the dashboard.
    This backlog, in combination with retry attempts, resulted in elevated latency"; scaling
    control-plane concurrency fixed it at about 15:30. Services "that had entered a bad state"
    needed restarts until 17:06.
- **Levers.** A fault that fails and recovers on a cycle, so a mitigation looks like it worked
  (lever 2). A coincidental event that suggests the wrong class of cause (lever 3). A cause that
  must be stopped at the source *and* cleaned up where it already landed (lever 1). A backlog with
  retries that keeps a service down after the fix (lever 4).

## Cloudflare, 20 February 2026: an empty parameter read as "all"

Source: [Cloudflare outage on February 20, 2026](https://blog.cloudflare.com/cloudflare-outage-february-20-2026/).

- **What happened.** A new cleanup task asked the API for `/v1/prefixes?pending_delete`. The
  server only filtered when the parameter had a value, so "the API server interprets this as a
  request for all BYOIP prefixes" and the task "began systematically deleting all BYOIP prefixes
  and all of their related dependent objects". About 1,100 of 4,306 prefixes were withdrawn
  between 17:56 and 18:46 UTC.
- **What misled them.** The post names nothing that misled the responders. Detection was slow:
  the first engagement was for failures on one.one.one.one at 18:13, and the cause was identified
  at 18:46, 50 minutes in. Customers were in mixed states: some "could toggle some prefixes but
  not others".
- **Mitigations.**
  - Stopping the task at 18:46 only stopped further damage; what was deleted stayed deleted.
  - Self-service re-advertising from the dashboard (19:19) worked for withdrawn prefixes but not
    for about 300 whose service bindings were gone: "they could not toggle their prefixes in the
    dashboard".
  - Those needed "a global configuration update ... to reapply the service bindings", 21:08 to
    23:03, the slowest step. A snapshot rollback system "is not in Production today".
- **Levers.** Stopping or reverting the cause does not restore state that was already destroyed or
  propagated; the cleanup is a second, slower action (lever 1). A tool call with a missing argument
  must be rejected, never read as "everything" (a rule for our own tool API, already true: every
  mitigation names one service).

## GitHub, October 2026 availability report

Source: [GitHub availability report: October 2026](https://github.blog/news-insights/company-news/github-availability-report-october-2026/).

- **5 October, a failover into a region without capacity.**
  - A partial network failure cut one region off from its databases. "Instead of failing fast,
    the service waited for those calls to time out. The waiting calls piled up until the service
    ran out of memory and restarted."
  - Backfired: "Jobs then shifted to the same service in a healthy region", which "did not have
    enough capacity for the extra demand and began failing too".
  - Did not help: "We redeployed the service that assigns jobs to GitHub-hosted runners, but it
    did not recover." The fix was to fail databases over "one service at a time, and added
    capacity".
- **7 October, the same outage twice.**
  - A replacement machine with outdated records was elected leader and "sent writes for several
    core databases to those retired servers". Writes recovered when another machine became leader,
    which looked like a fix.
  - The pause did not hold: "an automated maintenance task did not honor a pause on maintenance
    and triggered another election", and "because the new machine had not yet been removed, it
    became leader again". The cause was only removed after the second outage.
- **19 October, synchronized retries.** After a cache connection loss, "every server running that
  service then retried those connections at the same time", saturating a shared link. Routing
  away from some cache servers was not enough: "the link was still over capacity".
- **21 October, removing overloaded servers spread the overload.** "We took the overloaded servers
  out of service, and their traffic moved to other servers. Those servers then became overloaded
  too, and the problem spread to more servers over the following hour." Failed requests reconnected
  immediately, which kept the load up.
- **Levers.** Failover and removing capacity move load onto what is left; without headroom there
  the outage spreads (lever 1). A recovery that is really a coincidence, with the cause left in
  place, comes back (lever 2). Retries sustain an overload after its trigger is gone (lever 4).

## AWS us-east-1, 19-20 October 2025: a recovery that collapsed under its backlog

Source: [Summary of the Amazon DynamoDB Service Disruption in Northern Virginia](https://aws.amazon.com/message/101925/).

- **What happened.** A race between two DNS Enactors left "an incorrect empty DNS record" for the
  regional DynamoDB endpoint, which "the automation failed to repair". DNS was restored by hand at
  2:25 AM PDT.
- **What misled them / what the fix did not fix.**
  - EC2 did not recover with DynamoDB. The droplet workflow manager had to re-establish leases for
    the whole fleet at once: the work "took long enough that the work could not be completed before
    they timed out", and it "entered a state of congestive collapse". "This situation had no
    established operational recovery procedure."
  - Health checks on new instances were "alternating between failing and healthy", so load
    balancer nodes were "removed from DNS, only to be returned to service when the next health
    check succeeded".
- **Mitigations.**
  - Helped: at 4:14 AM "engineers throttled incoming work and began selective restarts", which
    "cleared out the DWFM queues". Throttles were relaxed only from 11:23 AM, after the backlog
    had drained.
  - Backfired (automatic): "automatic AZ DNS failover" took healthy capacity out of service, and
    applications failed "if the remaining healthy capacity was insufficient". Engineers "disabled
    automatic health check failovers" at 9:36 AM.
  - Lambda throttled asynchronous work "to prioritize latency-sensitive synchronous invocations".
- **Levers.** After the cause is fixed, the backlog keeps the system down until someone sheds load
  and drains it, and the throttle has to be lifted afterwards (lever 4). Failover on a flapping
  signal removes capacity that was healthy (levers 1 and 2).

## Microsoft 365, 12-13 November 2026: restarts that fell over when traffic returned

**The full post-incident report is not published yet.** Microsoft's 13 November statement ends
"We will provide a full post-incident report once our review is complete"
([BetaNews, quoting Microsoft on X](https://betanews.com/article/microsoft-365-outage-network-upgrade/)).
What follows is Microsoft's own advisory text for incidents EX1550543 and MO1550821 as quoted by
the linked outlets, not a technical postmortem; re-read it against the report when it appears.

- **What happened.** The outage began at 16:17 UTC on 12 November with Exchange Online and spread
  to Teams, SharePoint, Copilot and Defender ([CIO](https://www.cio.com/article/4248249/microsoft-struggles-to-get-m365-services-back-online-after-widespread-outage.html)).
  Microsoft's stated cause: "The incident was introduced by an issue during an earlier network
  capacity upgrade that surfaced following a recent network change"
  ([BetaNews](https://betanews.com/article/microsoft-365-outage-network-upgrade/)). On the servers,
  "a process ... responsible for establishing secure connections becomes overwhelmed, causing the
  servers to stop processing requests"
  ([CIO](https://www.cio.com/article/4248249/microsoft-struggles-to-get-m365-services-back-online-after-widespread-outage.html)).
- **What misled them.**
  - The first diagnosis was a traffic surge. It was revised within the hour: "the elevated load
    isn't driven by an increase in traffic, but by a number of servers being unexpectedly
    unavailable; straining the remaining infrastructure"
    ([BetaNews, quoting @MSFT365Status](https://betanews.com/article/microsoft-365-outage-network-upgrade/)).
  - An attack was suspected publicly and ruled out: "a technical issue not related to cyber or
    AI / agents" ([BetaNews](https://betanews.com/article/microsoft-365-outage-network-upgrade/)).
- **Mitigations.**
  - Backfired (automatic): servers that failed health checks were pulled out of service, and their
    traffic moved to the remaining machines, which then failed too
    ([Moneycontrol](https://www.moneycontrol.com/technology/microsoft-outage-company-says-patch-is-improving-server-stability-after-earlier-fixes-failed-to-hold-article-14079404.html)).
  - Looked like it worked, then did not: restarts and traffic rerouting gave early gains and "did
    not hold" ([Moneycontrol](https://www.moneycontrol.com/technology/microsoft-outage-company-says-patch-is-improving-server-stability-after-earlier-fixes-failed-to-hold-article-14079404.html));
    overnight Microsoft said its fixes were "not taking as expected"
    ([CIO](https://www.cio.com/article/4248249/microsoft-struggles-to-get-m365-services-back-online-after-widespread-outage.html)).
  - The mitigations added load: "As we've applied our current ongoing mitigation actions, we've
    observed a surge in outbound call volume from our routing services to our backend servers",
    with "heightened volume due to traffic rebalancing actions that we have taken"
    ([CIO](https://www.cio.com/article/4248249/microsoft-struggles-to-get-m365-services-back-online-after-widespread-outage.html)).
  - Helped: a patch to "an upstream authentication/routing configuration component"
    ([Moneycontrol](https://www.moneycontrol.com/technology/microsoft-outage-company-says-patch-is-improving-server-stability-after-earlier-fixes-failed-to-hold-article-14079404.html)),
    added capacity, and holding traffic back: "Given the scale of demand, we restored services
    gradually, validating stability at each stage. While this took longer, it helped ensure a
    stable restoration" ([BetaNews](https://betanews.com/article/microsoft-365-outage-network-upgrade/)).
    A day later they were "still draining queued messages and rebalancing traffic"
    ([a customer help page reproducing the MO1550821 advisories](https://thersac.icts.thers.ac.jp/hc/en-us/articles/64262985209881-November-13-2026-Microsoft-365-Outage-MO1550821)).
- **Levers.** Removing unhealthy capacity moves its load onto what is left (lever 1). A restart
  into full traffic recovers briefly and falls over again; it needs load held back while it comes
  up (levers 1, 2 and 4). A traffic-shaped symptom that is not a traffic cause (lever 3).

## AWS us-east-1, 19-20 October 2025, read again: one shared cause, and capacity that could not be launched

Source: the same [summary](https://aws.amazon.com/message/101925/), read again on 14 Nov 2026 for
round 12. The entry above covers the recovery; this one covers two things it left out.

- **One cause, many services that do not call each other.** The trigger was name resolution for
  one shared endpoint: "a latent race condition in the DynamoDB DNS management system that
  resulted in an incorrect empty DNS record for the service's regional endpoint". The effect was
  everywhere at once: "customers and other AWS services with dependencies on DynamoDB were unable
  to establish new connections to the service". Each victim failed in its own words: for Lambda
  "DynamoDB endpoint issues prevented function creation and updates", and EC2's host state
  checks "began to fail as the process depends on DynamoDB". None of that was fixed where it
  showed; the errors that came straight from DynamoDB ended with the one DNS repair at 2:25 AM.
- **Capacity that was asked for and did not arrive.** After the DNS repair, "new instance launches
  failed with either a "request limit exceeded" or "insufficient capacity" error", while
  "existing EC2 instances that had been launched prior to the start of the event remained
  healthy". Services that needed more capacity could not get it: ECS, EKS and Fargate saw
  "container launch failures and cluster scaling delays", and Lambda was left "under-scaled".
- **What they did while capacity was stuck.** "With EC2 launches still impaired, we throttled
  Lambda Event Source Mappings and asynchronous invocations to prioritize latency-sensitive
  synchronous invocations. By 11:27 AM, sufficient capacity was restored, and errors subsided. We
  then gradually reduced throttling".
- **Levers.** A fault in shared infrastructure outside the call graph shows on every service
  behind it, and is fixed once, at the shared component. A request for capacity can be accepted
  and never land; the responder has to notice, and either shed load or fix what blocks the
  launches. Both were built in round 12 and reverted (`LOOP.md`); they are the roadmap.
- **Where the simulator is simpler than the incident.** Our shared cause is a config change that
  a revert undoes in two minutes; AWS repaired its record by hand after 2 hours 37 minutes. Our
  blocked capacity is a quota or placement change on one node pool; AWS's was a lease backlog
  across the fleet. GitHub's 5 October 2026 outage above is the same shape from the other side:
  the healthy region "did not have enough capacity for the extra demand", and the fix was to add
  it.

## SREGym: failure modes we had not modelled

Source: Clark, Su, Pial et al., [SREGym: A Live Benchmark for AI SRE Agents with High-Fidelity
Failure Scenarios](https://arxiv.org/html/2605.07161v3) (arXiv 2605.07161v3, 30 Jul 2026). A
benchmark, not a postmortem: 90 problems on live Kubernetes applications. We read it on 14 Nov
2026, after level 4 was designed. We take its fault taxonomy as a checklist and copy no code or
text; quotes are from the paper.

- **Three failure modes** (section 2.4, "Failure Modes"). Metastable failures, which level 4
  already models from the incidents above. Concurrent failures, whose example pairs a
  user-facing fault with "a scheduler misconfiguration that makes an observability service pod
  unschedulable". And correlated failures: "failures in which multiple components fail at the
  same time because they share a common cause or dependency", where "the agent must recognize
  the correlations between the symptoms and connect them to the underlying root cause(s)".
- **Noise** (sections 2.1 and 2.4): "transient, self-recovering disturbances (e.g., a pod
  crashing and then being rescheduled and a few dropped requests)", which "are not failure root
  causes". In the evaluation two noise patterns run every five minutes for two minutes each.
- **How agents failed there** (section 3.1 and appendix D.3). With noise on, diagnosis fell by
  about ten points for the three strongest agent and model pairs. The stated reason: agents "take
  a greedy approach", they "always treat the first plausible anomaly as the target failure (which
  can be a noise)". In section 3.3, a fix follows a correct diagnosis in 68-89% of runs and a
  wrong one in 22-62%: agents often mitigate by pattern-matching a symptom.
- **What we took.** A correlated failure with one shared cause. A scheduling fault, but moved
  from an invisible bystander to the capacity the responder is about to rely on, where it tests
  a decision. Both were built as a level 6 in round 12 and reverted: the reference fell too far
  behind the oracle, and Opus was fooled by neither often enough to matter (`LOOP.md`). Noise
  was not built.
- **What we left out, and why.** Fail-slow, disk and kernel faults: the simulator models error
  rates per service, not latency or nodes.

## Background: why a fixed system can stay down

Bronson et al., [Metastable Failures in Distributed Systems](https://sigops.org/s/conferences/hotos/2021/papers/hotos21-s11-bronson.pdf)
(HotOS 2021), name the pattern the incidents above share: a trigger pushes a system into a bad
state, and a sustaining effect (most often retries) keeps it there after the trigger is removed.
Recovery needs load shed or capacity added, not another fix of the trigger.

## What the levers become in the simulator

| Lever | Rule | Incidents |
| --- | --- | --- |
| Retry storms and recovery dynamics | Callers retry failed calls; a service that runs hot stays overloaded after its fault is fixed until load is shed or capacity added, and a throttle left on keeps costing | AWS 2025 (DWFM), Cloudflare 2025 (dashboard), GitHub 19 and 21 Oct 2026, metastable failures paper |
| Mitigations that backfire | A restart, rollback or failover fails requests while it runs; on a hot, retried service that tips it over, and a failover onto a smaller standby overloads it | Microsoft 2026 (restarts), GitHub 5 Oct 2026 (failover), GitHub 21 Oct 2026, AWS 2025 (NLB failover) |
| Intermittent faults | A generated file is good or bad every few minutes; a mitigation applied in a good phase looks like it worked; the cause must be stopped at the source and cleaned up where it landed | Cloudflare 2025, GitHub 7 Oct 2026, Cloudflare Feb 2026 |
| Coincidental decoy of the wrong class | An unrelated event (status page down, a traffic bump within headroom) points at an attack or a surge | Cloudflare 2025, Microsoft 2026 |
| Correlated failure with one cause (roadmap, reverted in round 12) | A bad config on a shared resolver fails every service behind it; mitigating a victim fixes nothing and is charged | AWS 2025 (DynamoDB DNS), SREGym section 2.4 |
| Capacity that never arrives (roadmap, reverted in round 12) | A bad quota or placement change on a node pool: a `scale` is accepted and its replicas stay pending until the pool is fixed | AWS 2025 (EC2 launches), GitHub 5 Oct 2026, SREGym section 2.4 |
