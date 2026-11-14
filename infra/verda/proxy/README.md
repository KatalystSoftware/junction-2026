# The shared proxy on the Verda machine

One Caddy on `31.22.104.106` owns ports 80 and 443 and routes by hostname, so the machine can host
several apps. Each app is its own compose project with its own database and volumes; it joins the
Docker network `proxy` and publishes no ports.

| App | Address | Upstream on the `proxy` network |
| --- | --- | --- |
| Gap finder | `https://gapfinder.<base domain>/` and `https://31-22-104-106.sslip.io/` | `gapfinder-ui-1:8078`, on its own network |
| Since When | `https://since-when.<base domain>/` | `since-when-app:8078` |

The gap finder is the one exception to "apps join the `proxy` network": it was live first, so the
proxy joins its network `gapfinder_default` and its deploys need no change. If that project is ever
taken down with `docker compose down`, start it again before restarting the proxy.

Apply a change (run from a checkout, needs SSH access to the machine):

    infra/verda/proxy/deploy.sh

## The base domain

`BASE_DOMAIN` in [`proxy.env`](proxy.env) is the one setting: every app is `<app>.<base domain>`.
It is `31-22-104-106.sslip.io` today, which needs no DNS record.

To move to a real domain, create one wildcard record at the DNS provider, then change `BASE_DOMAIN`
and run `deploy.sh`:

    *.<base domain>.    A    31.22.104.106

For `BASE_DOMAIN=demo.example.org` that is `*.demo.example.org`. Caddy gets a certificate for each
hostname on its first request, over HTTP on port 80 (or TLS on 443), so no DNS provider key is
needed and the record must exist before the switch. The gap finder keeps answering on its first
address, `31-22-104-106.sslip.io`.

## Add an app

1. In the app's compose file, put the service that serves HTTP on the `proxy` network under a name
   of its own, and publish no ports:

   ```yaml
   services:
     web:
       networks:
         default:
         proxy: {aliases: [my-app-web]}
   networks:
     proxy: {external: true}
   ```

   Its start script creates the network when it is missing:
   `docker network inspect proxy >/dev/null 2>&1 || docker network create proxy`.
2. Add `sites/my-app.caddy`:

   ```
   my-app.{$BASE_DOMAIN} {
   	encode zstd gzip
   	reverse_proxy my-app-web:8080
   }
   ```
3. Run `infra/verda/proxy/deploy.sh`. The app is on `https://my-app.<base domain>/` once Caddy has
   its certificate, a few seconds after the first request.

Leave memory for the others: the gap finder is capped at about 13 GB, Since When at 3 GB, and the
machine also runs evaluation containers at times. Give each service a `deploy.resources.limits`.

On the machine the files are in `/srv/katalyst/proxy/`; certificates are in the volume `proxy_data`.
