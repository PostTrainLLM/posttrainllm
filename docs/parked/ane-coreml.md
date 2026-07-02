# Parked: ANE and CoreML

ANE/CoreML work produced useful measurements and negative results. It is parked
until a shipped specialist needs battery/perf optimization.

Do not spend near-term time on:

- new ANE conversion experiments
- chunking redesigns
- CoreML serving polish
- int8 handoff work

Reopen when a candidate specialist is already good enough and the bottleneck is
runtime performance, power, or packaging.
