# Load Balancing Strategies

## Round robin and weighted distribution

The simplest load balancer distributes requests to backends in rotation, so each server
receives an equal share. When servers differ in capacity, a weight per backend scales the
share up or down without changing the algorithm. Round robin ignores how long each
request runs, so a backend that receives several slow requests can fall behind while
others idle. Weighted round robin is the standard first step when hardware is
heterogeneous but request cost is roughly uniform.

## Least connections and latency

Least-connections balancing sends each new request to the backend with the fewest active
connections, which naturally adapts to requests of varying duration. It outperforms round
robin when some requests are much slower than others, because a busy backend stops
receiving new work until it drains. Some balancers track a smoothed latency score and
pick the fastest responding backend instead of the least loaded one. The two metrics
diverge when a backend is fast but temporarily saturated, so the choice depends on
whether queue depth or response time is the better predictor of user-perceived delay.

## Session affinity

Stateful applications that keep a session in server memory need requests from one client
to reach the same backend consistently. Sticky sessions achieve this by hashing the
client address or by setting a cookie that pins the client to a backend. Affinity
simplifies application code but weakens failover, because a backend failure drops the
sessions it held unless the state is replicated elsewhere. The cleaner architecture
moves session state into a shared store, letting any backend serve any request and
removing the need for affinity altogether.

## Health checks and failover

A health check probes a backend on a schedule and removes it from rotation after a set
number of consecutive failures. Passive checks watch real traffic for connection errors
or timeouts, while active checks send synthetic requests to a dedicated endpoint. Passive
checks add no extra load but only learn about a dead backend after a real user has
already suffered the failure. Active checks react faster but must be tuned so that a
brief spike does not flap a healthy backend in and out of the pool.

## Global and DNS balancing

At larger scale, a layer in front of several regional load balancers distributes traffic
by geography or by latency. DNS-based balancing returns different addresses to different
clients, which is cheap but limited by caching: a resolver may hold a stale answer long
after a region goes down. Anycast routing advertises one address from many locations and
lets the network steer each client to a nearby entry point. Both approaches need
region-level health signals, because a centrally healthy pool can still contain an
unreachable region.