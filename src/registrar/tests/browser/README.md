# Browser regression tests

Run from this directory:

```sh
npm ci
npx playwright install chromium
npm test
```

The DNS tests load the production JavaScript modules and the same Alpine CSP
version used by the registrar. They use a minimal form fixture, real keyboard
change events, and local request interception. No Django server, database, or
external service is needed. These tests cover client-side form switching;
server-rendered markup and the USWDS modal implementation are outside their scope.
