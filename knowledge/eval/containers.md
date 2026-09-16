# Containerizing Python Applications

## Images and layers

A Docker image is built from a layered file system, where each instruction in the
Dockerfile creates a layer that is cached and shared across builds. Instructions that
change frequently should sit at the bottom of the file so upstream layers stay cached.
The official Python image supports slim and alpine variants; slim images keep glibc
and package many prebuilt wheels, while alpine images are smaller but often force
source compilation of binary dependencies. Prefer slim over alpine for Python projects
for that reason.

## Multi-stage builds

A multi-stage build uses several FROM statements in one Dockerfile. The first stage
compiles assets and installs build dependencies, and the final stage copies only the
built result and the runtime requirements. This keeps runtime images dramatically
smaller because compilers, headers, and scratch files never reach the final artifact.
Each stage should name its base and tag a clear version, since unpinned base images
produce unreproducible builds.

## Running Python in containers

The container should run the application as an unprivileged user instead of root.
Debian based images provide a useradd mechanism at build time, and the CMD should point
at the entrypoint script. Environment variables carry configuration while secrets
should arrive through mounted files or an injected secret store rather than baked into
the image, because image layers are readable by anyone with image access. Health checks
declared in the image compose with orchestrators so a dead worker gets recycled
automatically.

## Networking fundamentals

Containers on the same bridge network resolve each other by service name. A published
port maps a container port to a host port with -p, and the mapping must not be exposed
wider than needed. Inter-container traffic that does not need host access should stay on
the private bridge network instead of the host network. Logs are written to standard
output and collected by the platform, so the application should not try to manage its
own log files inside the container.

## Dependency management in containers

Installing dependencies with a lock file inside the image makes builds reproducible.
The projector tooling used for Python projects installs from a lockfile and caches the
first phase as a separate layer so dependency resolution does not rerun on every code
change. Wheels are prioritized over source distributions before build tools are needed.
The whole point is that a container built today from the same commit produces the same
image tomorrow, and any change in the image is a deliberate, diffable change.

## Image size and efficiency

Layer count matters less than layer content. Merging a dozen RUN commands into one
produces a single layer that is easy to cache and avoids packing intermediate package
manager state into the final blob. The scratch base image starts from nothing, which
is perfect for compiled single binaries such as Go or Rust applications, while Python
and Node applications need at least a runtime base. Distroless images remove the
package manager and shell, cutting attack surface for production while keeping a
working runtime. Whatever the base, the image should be rebuilt and pushed only after
tests pass in CI, so the registry never sees a known-bad image.

## Resource management

Every container should declare its resource needs and limits, because a single runaway
worker can starve the host and take the whole platform with it. CPU limits throttle
contention, and memory limits trigger the kernel OOM killer against the offending
container instead of killing an unrelated process. Restarts, however, must not be the
first response to bad behaviour; a container that OOM loops is unhealthy and should be
flagged, not silently rescheduled forever. Logs and metrics belong outside the
container lifecycle, captured by the platform, so debugging does not require entering
a rotting container the instant it dies.

## Orchestration basics

An orchestrator reconciles the declared state of the workload with the observed state
of the cluster. Deployments describe how many replicas of a service must run, and a
replica set converges reality toward that number when a node fails or a pod is
evicted. Rolling updates replace old pods gradually, so a broken image surfaces on a
fraction of traffic before the remaining replicas are swapped. Service discovery is
handled by the platform's own DNS, so containers address each other by service name
and never need hard-coded host addresses. Secrets, configuration, and resource limits
are all declared as objects the orchestrator reconciles, keeping the human out of the
critical rebuild path.