# Opportunity Name (Opportunity Record Template)

## Metadata

| Key             | Value                                  |
|-----------------|----------------------------------------|
| ID              | CR0000                                 |
| Type            | Opportunity                            |
| Status          | Active                                 |
| Contributors    |                                        |
| Platforms       |                                        |
| Tactics         |                                        |
| Techniques      | [T0000]                                |
| Procedures      | [TRR0000.XXX.X]                        |

## Overview

The procedure this opportunity addresses, and why detecting it matters.

## Opportunity

The observable behavior that indicates the procedure, and why it does.

Describe what could be detected, not how any one environment would detect it.
Name the observable — "a directory replication request from a host that is not
a domain controller" — rather than a telemetry source, event ID, or query.
Those depend on what each organization collects, and they belong in the
coverage record that implements this opportunity. Where the procedure's
Technique Research Report has a Detection Data Model, say which part of it this
opportunity relies on.

## Considerations

Legitimate activity that produces the same observable, and anything else an
engineer should weigh when deciding whether this opportunity suits their
environment. Keep it general: specific exclusions belong in an implementation.

## References

- [Reference 1]

[T0000]: https://attack.mitre.org/techniques/
[TRR0000.XXX.X]: https://github.example.com/<org>/techniques/tree/main/reports/trr0000/xxx
[Reference 1]: https://www.microsoft.com
