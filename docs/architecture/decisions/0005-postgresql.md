# 5. PostgreSQL

Date: 2022-08-09

## Status

Accepted

## Context

Our choices of which database engine to use are presently limited by our desire to use cloud.gov for deployment.

Cloud.gov supports MySQL, PostgreSQL, and Oracle.

Oracle may be subject to licensing fees.

## Decision

To use PostgreSQL.

## Consequences

All three options are approximately equally capable. The number of CVEs filed against each project differs, but not by any order of magnitude.

The advanced administrative features of each database are not available in cloud.gov, so there is little reason to prefer one option over any other.
