# Content Delivery Networks

## Edge caching fundamentals

A content delivery network terminates requests at hundreds of geographically
distributed edge nodes instead of letting every visitor hit the origin server. The
edge serves cached copies of static objects and forwards only the rest to the origin,
so far-flung users see low latency even when the origin sits on one continent. Cache
keys are typically the request URI plus the host header, and vary subtly when
negotiated content or query parameters are involved. Cache misses cost an extra
round trip to the origin and a fill, which is why cache ratio, the fraction of requests
served from the edge, is the headline operational metric.

## Cache-control and TTLs

The TTL of an object decides how long an edge may serve it before revalidating with
the origin. Long TTLs on versioned asset bundles make them effectively immutable, while
HTML pages get short TTLs with revalidation via conditional requests. A stale-then-
revalidate policy lets the edge serve a slightly stale copy in parallel with fetching a
fresh one, hiding origin latency entirely on revalidation. Purge and invalidation
mechanisms exist so an accidental mis-set TTL does not force the operator to wait out
a long expiry across thousands of edges.

## Origin shielding and collapse

Without protection, a flash of popularity can send a thundering herd of simultaneous
cache misses at the origin. Origin shield nodes front one origin each and collapse the
duplicate fills so a hundred edge misses become a single origin request. Cache
collapse serializes identically keyed fills at the shield, sacrificing a little fill
latency for a dramatic reduction in origin load. This is where CDN behaviour meets
application caching: an origin that returns uncacheable headers bypasses the shield
and invites the very stampede it was built to prevent.

## Tiered routing

Anycast advertises the same IP from every edge location and lets the internet routing
table steer clients to the nearest node, enabling connection reuse and fast failover
when a datacenter disappears. Tiered routing then walks up the hierarchy from the edge
toward a regional cache and only then the origin, so many requests stop one hop short
of the origin. Edge nodes trade warm copies with their tier parents, keeping the
hierarchy warm without each edge doing a cold fill from the origin. The routing tier
must also drain and re-shield capacity during maintenance windows, since a shielded
origin cannot survive an unplanned edge evacuation.

## Security at the edge

CDNs often absorb more than cache hits; they terminate TLS, absorb volumetric
reflections, and enforce rate limits before the request ever reaches the origin.
Web Application Firewall rules running at the edge block SQL injection and cross-site
scripting payloads at scale, because the attack has to reach the origin to succeed
and the edge is much closer. If the WAF logic is buggy, the false-positive rate
becomes visible immediately, which is why the rules are usually staged in a
report-only mode before switching to enforcement. When a DDoS wave arrives, the edge
is the first resilient defence, and the tiered caching simply stops working, turning
the advantage of serving a stale object from anywhere in the world into a hard
availability guarantee.