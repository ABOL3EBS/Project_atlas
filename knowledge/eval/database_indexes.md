# Database Index Design

## B-tree versus hash indexes

B-tree indexes keep entries in sorted order, which makes them the default for equality
and range predicates alike. A range scan such as all orders between two dates walks
adjacent leaves, while a hash index can only answer an exact equality match and cannot
satisfy ordering. Most relational engines therefore default to B-tree and reserve hash
indexes for narrow, hot equality lookups. The planner compares the estimated cost of an
index walk against a sequential scan and picks whichever it expects to be cheaper, which
is why a selective predicate on a large table usually chooses the index.

## Composite index column order

A composite index on multiple columns only helps when the leading column appears in the
predicate. Placing the most selective and most frequently filtered column first lets the
index eliminate rows immediately. Indexes on the trailing columns alone are not usable
for a leading-column lookup, so teams sometimes add a second index that begins with the
other column. The rule of thumb is to lead with the equality column and trail with the
range column, because the range column cannot be seeked past a gap in the leading
equality.

## Covering indexes

When an index contains every column a query needs, the engine can answer entirely from
the index and never touch the table heap. These covering indexes eliminate the random
heap lookups that dominate read cost on spinning disks and still matter on solid state
drives under heavy concurrency. The trade-off is index size and write amplification:
every covered column widens the index and every insert updates it. A projection index
that covers the handful of hottest reporting queries often pays for itself, while
covering everything bloats storage for little gain.

## Index maintenance cost

Indexes are not free. Every insert, update, and delete must maintain every index that
covers the changed columns, so a table with a dozen indexes writes far more than one
with three. Unused indexes silently tax every write while never helping a read, which is
why monitoring index usage statistics and dropping dead indexes is routine hygiene. After
a large bulk load it is often faster to drop non-essential indexes, load the data, and
rebuild them afterward than to maintain them row by row during the load.

## When indexes mislead

The planner can be misled by stale statistics or by correlated columns it treats as
independent. A plan that chooses a nested loop over an index becomes pathological when
the estimated row count is orders of magnitude too low. Extended statistics, fresher
sampling, and occasionally an explicit hint correct the estimate. Adding more indexes is
not the fix for a bad plan; the fix is giving the planner accurate information or
rewriting the query so the cost model sees the true selectivity.