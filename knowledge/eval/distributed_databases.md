# Distributed Databases

## Sharding

Sharding splits one logical table across several machines by a shard key, so each
server holds a subset of the rows and the write load spreads evenly. A hash shard key
distributes rows uniformly but scatters rows that share a natural grouping, forcing an
application to gather results from every shard for range scans. A range shard key keeps
ordered runs on one machine but can concentrate hot traffic on a single shard when the
data clusters around recent timestamps. Choosing the key means trading write
distribution against how often queries cross shard boundaries. Once a table is sharded,
resharding is expensive, so the key is usually chosen for the few query shapes that
matter most.

## Replication models

Replication places copies of the data on multiple nodes. Single-leader replication
sends every write to one leader and fans the change out to followers, giving a simple
way to reason about ordering but a single point of performance. Multi-leader systems
accept writes on several nodes and must resolve conflicts when two leaders write to the
same key concurrently; without care, those conflicts produce diverging data. Leaderless
replication reads from several replicas and quorum arithmetic decides how many must
answer, trading availability for consistency. The lag between a leader accepting a
write and a follower reflecting it is the source of read-your-own-writes problems.

## Consistency and availability

Network partitions are not rare edge cases during wide-area operation; they are a
scheduled event. An idealized distributed system can either keep every replica
consistent at the cost of refusing writes during a partition, or keep accepting writes
at the cost of letting replicas diverge. Strong consistency reads require talking to a
quorum, which raises latency. Many systems default to eventual consistency and expose
strong reads as an option paid for in latency, letting the application choose per
query. Comparing the durability and visibility guarantees of each option is the core
design decision in any replicated store.

## Write-ahead logs across machines

Each node must still persist its own durable log before acknowledging a write, exactly
as a single node does, and the replicas replay that log to catch up. A dangling
transaction on one node that committed elsewhere is the classic split-brain
inconsistency, so atomic commit protocols coordinate the decision across every node
that took part. Two-phase commit guarantees that either all participants commit or all
abort, but it blocks waiting on a participant that has crashed. Modern systems prefer
a replicated log such as the ones used by consensus algorithms, because the log itself
is the source of truth for ordering and can be replayed from any healthy follower.

## Read scaling and hot partitions

Follow replicas absorb read traffic that the leader does not need to serve, which is
the cheapest way to scale read-heavy workloads: add replicas, point more reads at them,
and pay nothing on the write path. The catch is replication lag, so a user who reads
from a replica immediately after writing may not see their own write; applications
often pin session reads to the leader or wait out a staleness bound. Writes cannot be
scaled by adding replicas, only by splitting writes across shards, which is why a
single hot key that receives an outsized share of traffic becomes the bottleneck no
number of replicas can fix. Sharding a table around a planned hot key, then accepting
that the shards are uneven, is where distributed-database tuning stops resembling
single-node tuning and starts resembling capacity planning.