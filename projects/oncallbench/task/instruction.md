You are the on-call engineer for an online shop's backend. You have just been paged: customers
are seeing errors. Work the incident through the `ops` MCP tools and keep the lost revenue for
the shift as low as you can.

## The job

- The shift lasts 120 simulated minutes from the page (minute 0). Telemetry reaches back three
  hours before the page.
- Customer-facing (edge) services earn revenue per minute; every failed request at an edge
  service loses its share of that revenue. Edge services call app services, which call data
  services. A service that fails passes failures to its callers (a hard dependency passes all of
  them, a soft one about 30%).
- When nothing is wrong, an edge service fails well under 1% of its requests. Anything above
  that is a fault costing money, however steady it looks.
- Several things can be broken at once, and new faults can start during the shift. Find every
  cause and apply the mitigation that fits it. A symptom on one service is often caused by a
  service it depends on.
- Not every alert or recent change is a cause. A mitigation on a service that did not need it
  costs money and can disrupt that service.
- Everything you need is in the tools; nothing is on disk. A shift accepts at most 400 tool calls
  (`get_status` does not count).

<!-- BRIEFING -->

Your score is how much of the avoidable cost you avoided: doing nothing scores 0, the on-call
reference run scores 1.
