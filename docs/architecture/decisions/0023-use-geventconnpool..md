# 22. Use geventconnpool library for Connection Pooling

Date: 2023-13-10

## Status

In Review

## Context

When sending and receiving data from the registry, we use the [EPPLib](https://github.com/cisagov/epplib) library to facilitate that process. To manage these connections within our application, we utilize a module named `epplibwrapper` which serves as a bridge between getgov and the EPPLib library. As part of this process, `epplibwrapper` will instantiate a client that handles sending/receiving data.

At present, each time we need to send a command to the registry, the client establishes a new connection to handle this task. This becomes inefficient when dealing with multiple calls in parallel or in series, as we have to initiate a handshake for each of them. To mitigate this issue, a widely adopted solution is to use a [connection pool](https://en.wikipedia.org/wiki/Connection_pool). In general, a connection pool stores a cache of active connections so that rather than restarting the handshake process when it is unnecessary, we can utilize an existing connection to avoid this problem. 

In practice, the lack of a connection pool has resulted in performance issues when dealing with connections to and from the registry. Given the unique nature of our development stack, our options for prebuilt libraries are limited. Out of our available options, a library called [`geventconnpool`](https://github.com/rasky/geventconnpool) was identified that most closely matched our needs. 

## Considered Options

**Option 1:** Use the existing connection pool library `geventconnpool` as a foundation for connection pooling.

**Option 2:** Write our own connection pool logic.

**Option 3:** Modify an existing library which we will tailor to our needs.

## Tradeoffs

**Option 1:**
Pros: 
- Subtantially saves development time and effort. 
- It is a tiny library that is easy to audit and understand.
- This library has been used for [EPP before](https://github.com/rasky/geventconnpool/issues/9)
- Uses [`gevent`](http://www.gevent.org/) for coroutines, which is reliable and well maintained.
-  
- Cons: May not be tailored to our specific needs, could introduce unwanted dependencies.

**Option 2:**
- Pros: Full control over functionality, can be tailored to our specific needs.
- Cons: Requires significant development time and effort, needs thorough testing.

**Option 3:**
- Pros: Savings in development time and effort, can be tailored to our specific needs.
- Cons: Could introduce complexity, potential issues with maintaining the modified library.

## Decision

We have decided to go with option 1. New users of the registrar will need to have at least one approved application OR prior registered .gov domain in order to submit another application. We chose this option because we would like to allow users be able to work on applications, even if they are unable to submit them. 

A [user flow diagram](https://miro.com/app/board/uXjVM3jz3Bs=/?share_link_id=875307531981) demonstrates our decision.

## Consequences