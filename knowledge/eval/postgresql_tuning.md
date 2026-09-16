# PostgreSQL Performance Tuning

## Memory settings

The most impactful setting in a dedicated database server is shared_buffers. A common
starting point is 25 percent of system RAM, capped near a few gigabytes on smaller
instances. On top of that, work_mem controls how much memory each sort or hash join may
use; it defaults to four megabytes per operation and should be raised carefully because
it multiplies by the number of concurrent queries. PostgreSQL derives a default for
effective_cache_size from the OS cache, which helps the planner estimate whether index
reads would be served from disk.

## Indexes and query plans

The planner chooses an index scan only when it estimates that returning the matching
rows is cheaper than sequential scan. For selective equality filters a B-tree index is
the right tool. Range queries and ordering benefit from the same B-tree because index
entries are naturally sorted. GIN indexes accelerate full-text and array containment
checks. If a query distills a table many times over, comparing the EXPLAIN ANALYZE output
before and after adding an index is the honest way to measure the win.

## Vacuum and statistics

PostgreSQL never rewrites rows in place. Deleted tuples leave behind dead rows that must
be reclaimed by autovacuum, otherwise table bloat slows sequential scans and drives up
disk usage. Autovacuum also refreshes the planner statistics, and stale statistics are a
frequent cause of bad plans after large bulk loads. Recent PostgreSQL major versions
also maintain extended statistics across correlated columns, which improves estimates
for multi-column filters.

## Connection handling

Each active connection consumes a fixed slice of memory, so connection pooling matters
long before the CPU is saturated. A dedicated pooler such as PgBouncer in transaction
mode keeps a small number of server connections busy across many clients. Long-running
transactions hold snapshots open and block vacuum cleanup, so batches should commit
frequently and idle-in-transaction timeouts should be small.

## WAL and durability tuning

The write-ahead log guarantees crash safety, but synchronous_commit can trade some
durability for throughput. With synchronous_commit set to off, a shortcut taken by many
reporting workloads, a power failure may lose the most recent transactions. Increasing
checkpoint distances and raising max_wal_size reduce checkpoint frequency, which smooths
write latency spikes at the cost of more disk space. SSD storage makes most of these
trade-offs less painful than they are on spinning disks.

## Table and index bloat

Random writes to a table with many deleted rows confuse the planner's cost model.
A bloated table has far more pages than its live row count justifies, so sequential
scans become disproportionately expensive while still returning the same rows. The
pgstattuple extension quantifies bloat, and a careful VACUUM FULL rebuilds the table,
but it takes an exclusive lock and must be scheduled off-hours. Partial indexes that
target only frequently queried subsets shrink the index footprint and keep common
paths cache-resident.

## Partitioning and selectivity

Partitioned tables help when a query always filters on the partition key, because the
planner can prune partitions before scanning. Range partitioning by date is the most
common design for time-series data, with monthly or yearly boundaries matching the
retention policy. Partition pruning only works when the query predicate uses the
partition key directly; wrapping it in a function call defeats the pruning and turns
an elegant scheme into a sequential-scan disaster. Inherited old partitions can be
detached and dropped cheaply, which is why partitioned time-series tables never need
a VACUUM FULL.