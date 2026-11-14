# Alpine on purpose: on a musl image Harbor installs OpenCode's Node from the distro's packages
# instead of fetching nvm from raw.githubusercontent.com, so the GitHub hosts that would serve this
# repo's simulator and reference can be blocked (docker-compose.yaml, extra_hosts).
FROM alpine:3.22

RUN apk add --no-cache bash curl ca-certificates coreutils python3

WORKDIR /app
