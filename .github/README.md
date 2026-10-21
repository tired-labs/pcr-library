# TIRED Labs Detection Opportunities

A public library of opportunities to detect the procedures identified in the
[TIRED Labs TRR library].

An opportunity names the observable behaviors of a procedure — "a directory
replication request from a host that is not a domain controller" — and
deliberately stops there. It carries no telemetry sources, event IDs, or
queries, because those depend on what each organization collects.

## Using an opportunity

Read an opportunity alongside the procedure's Technique Research Report, and
decide how to cover the procedure in your own environment with the telemetry
you actually have. Record the result in your own coverage library: a coverage
record for a detection you built, or a gap record if you can't cover it.

Opportunities are alternatives, not a checklist. A procedure may have several;
one detection that reliably catches it is full coverage, and building every
opportunity would mostly add cost and duplicate alerts. Which ones to implement,
and how many, is your call.

[Insomnia] can show these opportunities over your own records, highlighting the
procedures where a detection path is already published but you have no record
of your own yet.

## Contributing

New opportunities and improvements are welcome. Keep them abstract: an
opportunity that names a telemetry source or contains a query has crossed into
implementation, which belongs in an organization's own records.

## Run your own coverage library

This repository's `main` branch is the public library of opportunities. The
template it is built from lives on the **`template` branch**. Deploy your own —
usually private, since your coverage records map what you can and cannot detect
— by following the [Deployment Guide].

[TIRED Labs TRR library]: https://library.threat-research.org
[Insomnia]: https://github.com/tired-labs/insomnia
[Deployment Guide]: https://github.com/<upstream-org>/<upstream-coverage-repo>/blob/template/docs/DEPLOYMENT.md
