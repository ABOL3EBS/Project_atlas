# Software Testing Practices

## The testing pyramid

A balanced test suite is shaped like a pyramid: many cheap, fast unit tests at the base,
a thinner layer of integration tests that exercise real components together, and a small
number of end-to-end tests at the top that validate a full user journey. The shape
matters because unit tests run in milliseconds and pinpoint failures, while end-to-end
tests are slow, flaky, and hard to localize when they break.

## Property-based testing

Edge cases are exactly where hand written examples miss behaviour. Property-based tests
declare an invariant that must hold for any generated input, such as average of a list
always lying between minimum and maximum. The framework generates hundreds of random
inputs and, when an example fails, shrinks it to the smallest counterexample for
debugging. Sorting, serialization round trips, and summing functions are all natural
candidates because they are pure and their invariants are easy to state.

## Test doubles

A test double stands in for a real dependency. Fakes are lightweight in-memory
implementations with real behaviour. Stubs return hard coded answers, and mocks record
the calls they receive so tests can assert interaction. The key distinction is that
asserting on implementation details makes tests brittle, so mocks should be limited to
the boundary of the system and asserted sparingly.

## Coverage and its limits

Coverage measures which lines executed, not whether behaviour is correct. A suite can
reach ninety percent coverage and still miss the fault paths that matter, particularly
error handling and boundary values. Treat coverage as a tripwire rather than a goal:
a coverage drop after a refactor signals that new code is untested, but pushing the
number upward with trivial assertions only creates false confidence.

## Determinism in tests

Tests must be reproducible. Time, randomness, filesystem paths, and network calls all
need explicit control, either by injecting a clock and a random source or by using
temporary directories per test. Tests that depend on global mutable state fail in an
order-dependent fashion that nobody can debug at three in the morning. Fast, isolated,
deterministic tests are what make a team confident enough to refactor constantly.

## Testing asynchronous code

Async code adds failure modes that sync tests never exercise, such as unhandled
background tasks, timeouts, and shared event loops. Tests should await the same public
API a caller uses, drive fake clocks to trigger timers instead of sleeping, and make
sure every spawned task completes before the test ends, otherwise teardown races
against running coroutines. When a system has a timeout, the test should simulate both
sides: a response that arrives in time and one that exceeds the deadline, asserting
the correct cancellation and cleanup path in each.

## Regression test discipline

A regression test is a new failing test that reproduces the observed bug before the
fix. It is written in the same change as the fix and stays green afterwards, so the fix
has a dedicated guard even if the surrounding suite changes. Bugs that cost a team a
day should get a test at the level closest to the root cause, which is usually a unit
test that exercises the internal function directly rather than an end-to-end test that
only demonstrates the symptom.