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
