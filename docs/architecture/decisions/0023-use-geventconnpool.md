# 22. Use geventconnpool library for Connection Pooling

Date: 2023-13-10

## Status

Accepted

## Context

When sending and receiving data from the registry, we use the [EPPLib](https://github.com/cisagov/epplib) library to facilitate that process. To manage these connections within our application, we utilize a module named `epplibwrapper` which serves as a bridge between getgov and the EPPLib library. As part of this process, `epplibwrapper` will instantiate a client that handles sending/receiving data.

At present, each time we need to send a command to the registry, the client establishes a new connection to handle this task. This becomes inefficient when dealing with multiple calls in parallel or in series, as we have to initiate a handshake for each of them. To mitigate this issue, a widely adopted solution is to use a [connection pool](https://en.wikipedia.org/wiki/Connection_pool). In general, a connection pool stores a cache of active connections so that rather than restarting the handshake process when it is unnecessary, we can utilize an existing connection to avoid this problem. 

In practice, the lack of a connection pool has resulted in performance issues when dealing with connections to and from the registry. Given the unique nature of our development stack, our options for prebuilt libraries are limited. Out of our available options, a library called [`geventconnpool`](https://github.com/rasky/geventconnpool) was identified that most closely matched our needs. 

## Considered Options

**Option 1:** Use the existing connection pool library `geventconnpool`.
<details open>
<summary>➕ Pros</summary>

- Saves development time and effort. 
- A tiny library that is easy to audit and understand.
- Built to be flexible, so every built-in function can be overridden with minimal effort.
- This library has been used for [EPP before](https://github.com/rasky/geventconnpool/issues/9).
- Uses [`gevent`](http://www.gevent.org/) for coroutines, which is reliable and well maintained.
- [`gevent`](http://www.gevent.org/) is used in our WSGI web server.  
- This library is the closest match to our needs that we have found.

</details>
<details open>
<summary>➖ Cons</summary>

- Not a well maintained library, could require a fork if a dependency breaks.
- Heavily reliant on `gevent`.

</details>

**Option 2:** Write our own connection pool logic.
<details open>
<summary>➕ Pros</summary>

- Full control over functionality, can be tailored to our specific needs.
- Highly specific to our stack, could be fine tuned for performance.

</details>
<details open>
<summary>➖ Cons</summary>

- Requires significant development time and effort, needs thorough testing.
- Would require managing with and developing around concurrency.
- Introduces the potential for many unseen bugs.

</details>

**Option 3:** Modify an existing library which we will then tailor to our needs.
<details open>
<summary>➕ Pros</summary>

- Savings in development time and effort, can be tailored to our specific needs.
- Good middleground between the first two options.

</details>
<details open>
<summary>➖ Cons</summary>

- Could introduce complexity, potential issues with maintaining the modified library.
- May not be necessary if the given library is flexible enough. 

</details>

## Decision

We have decided to go with option 1, which is to use the `geventconnpool` library. It closely matches our needs and offers several advantages. Of note, it significantly saves on development time and it is inherently flexible. This allows us to easily change functionality with minimal effort. In addition, the gevent library (which this uses) offers performance benefits due to it being a) written in [cython](https://cython.org/), b) very well maintained and purpose built for tasks such as these, and c) used in our WGSI server. 

In summary, this decision was driven by the library's flexibility, simplicity, and compatibility with our tech stack. We acknowledge the risk associated with its maintenance status, but believe that the benefit outweighs the risk. 

## Consequences

While its small size makes it easy to work around, `geventconnpool` is not actively maintained. Its last update was in 2021, and as such there is a risk that its dependencies (gevent) will outpace this library and cause it to break. If such an event occurs, it would require that we fork the library and fix those issues. See option 3 pros/cons.

## Mitigation Plan
To manage this risk, we'll:

1. Monitor the gevent library for updates.
2. Design the connection pool logic abstractly such that we can easily swap the underlying logic out without needing (or minimizing the need) to rewrite code in `epplibwrapper`.
3. Document a process for forking and maintaining the library if it becomes necessary, including testing procedures.
4. Establish a contingency plan for reverting to a previous system state or switching to a different library if significant issues arise with `gevent` or `geventconnpool`.