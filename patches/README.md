# HTTP cache semantics security patch

The public `http-cache-semantics@4.3.0` source still permits `max-stale` to
reuse responses that shared-cache rules prohibit. This workspace pins 4.3.0 and
applies the local patch so no-cache/non-storable responses, shared
`proxy-revalidate` responses, and shared `Set-Cookie` responses without an
explicit `public` or `immutable` opt-in always require validation.

`pnpm test:dependency-security` exercises 27 behavior cases against the package
resolved through Astro in `browser`. Set
`POSTTRAIN_CACHE_CONSUMER=docs-site` and run the same command to verify the
second Astro graph. The test covers policy serialization as well as normal
`max-stale` age and URL bounds.

Remove the patch only after upstream source fixes pass these tests through both
Astro graphs; the version number alone is not evidence of a fix.
