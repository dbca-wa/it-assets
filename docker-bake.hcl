# docker-bake.hcl — reproducible, multi-arch build config.
# Build (local, native platform, tagged :dev):  docker buildx bake local
# Build + push (multi-arch):                    docker buildx bake --push app
#                                                (needs a docker-container builder)
# Override variables at build time:             LOCAL_TAG=local IMAGE=ghcr.io/me/project docker buildx bake local
# Multi-arch with overrides:                    IMAGE=ghcr.io/me/project PLATFORMS=linux/arm64 docker buildx bake --push app
# Override a Dockerfile ARG:                    docker buildx bake --set app.args.PYTHON_VERSION=3.14-debian13-dev
# GitHub CI builds the "ci" target (see .github/workflows/multi-build.yml).

variable "IMAGE" {
  description = "Fully-qualified image name, without the tag."
  default     = "ghcr.io/dbca-wa/it-assets"
}

variable "TAG" {
  description = "Tag applied by the app/ci build targets."
  default     = "latest"
}

variable "LOCAL_TAG" {
  description = "Tag for a local development image."
  default     = "dev"
}

variable "PLATFORMS" {
  description = "Platforms used by the multi-arch targets."
  type        = list(string)
  default     = ["linux/amd64", "linux/arm64"]
}

group "default" {
  targets = ["app"]
}

# What to build. Exporter, cache and attestation policy belong to the targets
# that consume this, so local builds don't inherit CI-only behaviour.
target "_base" {
  context    = "."
  dockerfile = "Dockerfile"
}

# Local development: native platform, loaded into Docker, tagged :dev (default).
# No `platforms`: BuildKit builds for the builder's host platform,
# so the image always matches the machine running the build.
target "local" {
  inherits = ["_base"]
  tags     = ["${IMAGE}:${LOCAL_TAG}"]
  output   = ["type=docker"]
}

# Multi-arch image for the registry (manual release build & push or CI).
# Push-only target.
target "app" {
  inherits  = ["_base"]
  tags      = ["${IMAGE}:${TAG}"]
  platforms = PLATFORMS
  # Provenance + SBOM; attached on push (CI needs attestations + id-token permissions).
  attest    = ["type=provenance,mode=max", "type=sbom"]
}

# CI-only: GitHub Actions cache, and always refresh base images so any
# scheduled rebuild picks up upstream security fixes.
# Note that CI overrides tags in multi-build.yml via set: ci.tags=...
target "ci" {
  inherits   = ["app"]
  cache-from = ["type=gha"]
  cache-to   = ["type=gha,mode=max"]
  pull       = true
}
