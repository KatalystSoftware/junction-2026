# r7-l5-s101-sonnet-143147/aq-incident-5815b038__9t3WG3W

Level 5, seed 101, sonnet, score as run 0.0. The agent's closing message, verbatim:

All four edge services were at 0% errors when I ended the shift at minute 120, but I lost a lot of revenue getting there. Mobile-api was down for most of the shift, and I caused a second outage on it myself around minute 88.

**What was broken and what I did**
- **partner-api (the $22.7k/min service):**
  - **Cause:** quotes-svc deploy v149 broke the price formatter (a missing `currency` key).
  - **Fix:** I rolled it back at minute 33.
  - **Side effect:** The rollback pushed quotes-svc into a retry storm. I scaled it up and throttled it briefly, and partner-api was at 0% by about minute 60. I left quotes-svc at 8 replicas instead of its normal 6.
- **web-storefront, first fault:** a subscriptions-svc config change (cfg-16) made it generate an oversized rules file, which crashed emails-svc. I reverted the config at minute 44, and emails-svc recovered.
- **web-storefront, second fault:** a new address-svc config change (cfg-36, a schema bump to v3) started at minute 47 and caused decode errors. I reverted it at minute 79.
- **mobile-api:**
  - **Cause:** pricing-svc had been overloaded since before the page, and sms-svc then went into a retry storm.
  - **Fix:** I added replicas to both and throttled them to break the storms, then lifted the throttles around minute 83. It recovered.

**My mistake with pricing-svc:** pricing-svc's normal load is now about 2,900 requests per second, roughly three times what its normal replica count handles. Because I misread that, mobile-api was at 80–99% errors for most of the first 85 minutes. At minute 87 I scaled pricing-svc back to its normal 6 replicas, which brought the overload back. I rescaled it to 20 at minute 98, and mobile-api has been clean since about minute 105. pricing-svc is still at 20 replicas, which costs money but is what keeps it stable.

**Other things I left running:** sms-svc is back at its normal 8 replicas. Both of the config reverts and the one rollback were applied to services that needed them, so I don't expect any wasted-mitigation charges.

**Alerts I did not act on:** status-page (external) and cart-svc CPU were firing throughout and never affected an edge service.
