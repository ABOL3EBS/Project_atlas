# Nginx Configuration Guide

## Core configuration structure

Nginx reads configuration from an nginx.conf file composed of a main context and nested
event, http, server, and location blocks. The worker_processes directive sets how many
worker processes handle requests, and worker_connections caps the open connections each
worker may hold. A healthy default for a single machine is one worker per CPU core with
a few thousand worker connections, but the practical ceiling depends on memory and file
descriptor limits.

## Serving static files

Static file serving is where Nginx shines. Setting sendfile on lets the kernel copy
files from disk to the socket, bypassing the user space buffer. The tcp_nopush directive
delays the final packet until the whole response is ready so headers and body are sent
together, and tcp_nodelay is turned on for keepalive responses. Expires headers and
cache-control values should be set per location, aggressive for hashed assets and
revalidating for HTML documents.

## Reverse proxy patterns

A reverse proxy forwards matching requests to an upstream group of application servers.
The upstream block lists each server with optional weight and fail_timeout. Nginx load
balances across upstreams with a round-robin policy unless ip_hash or least_conn is
selected. The proxy_set_header block must pass X-Forwarded-For, X-Forwarded-Proto, and
the original Host so the application sees the client address and the scheme the client
actually used. Enabling proxy_buffering smooths slow upstream responses.

## TLS termination

TLS termination on Nginx requires a certificate chain and a private key. A strong
modern cipher set prefers TLS 1.3 and drops weak ciphers entirely. HTTP Strict Transport
Security should be sent with a long max-age so browsers refuse plain HTTP for the host.
Full handshakes are expensive, so session caching via the shared zone and session tickets
let returning clients resume a short handshake. Redirecting port 80 to 443 is trivial,
but the redirect must preserve the full request URI.

## Headers and logging

The error_log and access_log directives control what Nginx writes. The default combined
access log includes the client IP, timestamp, request line, status, bytes, and referer.
Caching access logs to tmpfs and enforcing periodic rotation prevents a busy host from
filling the disk. Security headers such as X-Content-Type-Options and
X-Frame-Options should be added globally in the http block rather than duplicated in
every server block.

## Caching and gzip

The proxy_cache directive stores upstream responses on disk keyed by the request URI,
and cache zones are configured in the http block before any server references them. A
cache miss forwards the request and stores the response, while a cache hit short
circuits the upstream entirely and can serve thousands of requests per second. Setting
proxy_cache_valid per status code controls freshness, and cache-control headers from
the upstream need to be respected or bypassed deliberately. Compressing responses with
gzip before they leave Nginx shrinks transfer sizes dramatically, but gzip must not be
applied to already compressed formats such as JPEG or ZIP, or it wastes CPU for nothing.

## Location matching rules

Nginx picks a location block with precise precedence. A prefix match using the caret
tilde operator wins outright over all other prefix and regex matches on the same
request. Next come regular expression locations, evaluated in file order from the top
of the configuration, with case sensitive matchers beating case insensitive ones.
Plain prefix locations are the weakest and only win when no regular expression matches.
Understanding this precedence table prevents the classic bug where a regex location
silently never runs because an earlier regex already matched, leaving developers to
debug why a path behaves differently when the block order changes.