# Verda infra for Junction 2026. Credentials come from sops:
#   sops exec-env ../../secrets/secrets.yaml 'tofu plan'
# State is local and gitignored, so run this from one machine.

terraform {
  required_providers {
    verda = {
      source  = "verda-cloud/verda"
      version = "~> 1.0"
    }
  }
}

provider "verda" {}

resource "verda_ssh_key" "hestia" {
  name       = "hestia-junction2026"
  public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIG/SXqqPAKNVWNRaO2boPf4DLl06hrVmbrzv5af2RXo5 hestia->verda junction2026"
}

resource "verda_ssh_key" "amp_runner" {
  name       = "amp-workspace-verda-runner"
  public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKAaxCTpvQhPYVYBjdTQphCNGAu1fB/l49vhcbTa6rZa amp-workspace-verda-runner"
}

# Harbor runs each trial in a Docker container, so the base image gets Docker on first boot.
resource "verda_startup_script" "docker" {
  name   = "junction2026-docker"
  script = <<-EOT
    #!/bin/sh
    set -eu
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io git
    systemctl enable --now docker
  EOT
}

# CPU runner for agent eval runs. Turin (Zen 5) is only available in FIN-03.
# Verda only injects ssh_key_ids at creation, so changing them replaces the instance.
# Teammates' keys were appended by hand to root's authorized_keys instead
# (github.com/{MikaelSiidorow,kahlstrm,duckymcduck2}.keys); redo that if the runner is recreated.
resource "verda_instance" "runner" {
  hostname          = "junction2026-runner"
  description       = "Junction 2026 agent eval runner"
  instance_type     = "CPU-TURIN.8V.32G"
  image             = "26.04.base"
  location          = "FIN-03"
  ssh_key_ids       = [verda_ssh_key.hestia.id, verda_ssh_key.amp_runner.id]
  startup_script_id = verda_startup_script.docker.id

  os_volume = {
    name = "junction2026-runner-os"
    size = 100
    type = "NVMe"
    # Most instance changes force replacement; keep the disk (and our eval results) when that happens.
    # A detached volume still costs money: delete it in the console once it's no longer needed.
    on_destroy = "keep_detached"
  }
}

# Render box for the submission videos (projects/videos). Recording a browser and rendering frames
# takes every core it is given, and on hestia that starved the other agents, so it runs here instead.
# It holds nothing worth keeping: the videos are copied back, and the disk goes with the instance.
resource "verda_instance" "render" {
  hostname      = "junction2026-render"
  description   = "Junction 2026 video rendering"
  instance_type = "CPU-TURIN.8V.32G"
  image         = "26.04.base"
  location      = "FIN-03"
  ssh_key_ids   = [verda_ssh_key.hestia.id, verda_ssh_key.amp_runner.id]

  os_volume = {
    name = "junction2026-render-os"
    size = 60
    type = "NVMe"
  }
}

# Clean box for rehearsing the AfterQuery judges' rerun of the on-call environment: a machine that
# has never seen this repo, so nothing in its README works by accident. It gets Docker and git and
# nothing else. It holds nothing worth keeping; remove it once the submission is in.
# Verda had no CPU type free in any location when it was made (Sat 14 Nov, evening), so it is the
# smallest type that was: 4 vCPU, 18 GB and a V100 it does not use, $0.24 an hour.
resource "verda_instance" "judge" {
  hostname          = "junction2026-judge"
  description       = "Junction 2026 judge rerun rehearsal"
  instance_type     = "1V100.4V"
  image             = "26.04.base"
  location          = "FIN-01"
  ssh_key_ids       = [verda_ssh_key.hestia.id, verda_ssh_key.amp_runner.id]
  startup_script_id = verda_startup_script.docker.id

  os_volume = {
    name = "junction2026-judge-os"
    size = 60
    type = "NVMe"
  }
}

output "runner_ip" {
  value = verda_instance.runner.ip
}

output "render_ip" {
  value = verda_instance.render.ip
}

output "judge_ip" {
  value = verda_instance.judge.ip
}
