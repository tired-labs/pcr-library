# Repository Design

This document explains how a coverage record library is put together: how it is
configured, how records are identified and validated, how provider integrations
attach, and how an organization stands up its own instance.

## Where this repo fits

The TIRED Labs ecosystem separates *research* from *coverage* from
*presentation*, and each lives in its own place:

- **TRR libraries** hold Technique Research Reports: how an attack technique
  works, the procedures that make it up, and the detection data models that
  describe the evidence it leaves behind. A TRR describes the technique itself
  and says nothing about any particular organization's detections.
- **Coverage record libraries** (this repository) track what a given
  organization actually detects or prevents, and where it has gaps.
- **Insomnia** is the dashboard. It reads one or more TRR libraries and one or
  more coverage libraries, joins them, and produces a unified view of research
  and coverage mapping.

The separation matters for a practical reason: research is shareable, coverage
is not. **A coverage record library is inherently internal.** It is a map of
what an organization can and cannot see, which is exactly what an attacker
would want. Instances are private by default and this template ships no example
records, because any realistic example would be organization-specific defensive
detail.

Each library is self-contained and unaware of any other. It produces a
well-formed `index.json` describing its own contents, and that is the whole of
its obligation. Repository name, base URL, and visibility are Insomnia
configuration, not repository configuration.

## Records

There are exactly three record types.

**Coverage** records describe coverage that exists. Every one names a
**provider** — the system supplying that coverage. Coverage that is not an
active detection, such as OS hardening or network segmentation, uses the
provider `Preventative`.

**Gap** records describe coverage that does not exist: the procedure was
assessed and cannot be covered. They name no provider, and the validator
rejects one that does.

**Opportunity** records describe a way a procedure *could* be detected, without
implementation detail. They are not coverage, so they name no provider either.

Detections are not a separate type. A detection is a coverage record whose
provider happens to be a detection platform.

### Opportunities

An opportunity names the observable behaviour that indicates a procedure — "a
directory replication request from a host that is not a domain controller" —
and deliberately stops there. The telemetry source, event IDs, query, and
tuning are what distinguish an implemented detection from an opportunity, and
they vary from one organization to the next, so they belong in the coverage
record that implements it. A practical test during review: an opportunity that
names a telemetry source or contains a query has crossed into implementation.

For the same reason, opportunities use only the core fields. Anything more
specific would describe one environment.

The public coverage library publishes opportunities for anyone to use. An
organization reads them alongside the procedure's Technique Research Report and
decides how to cover the procedure in its own environment, recording the result
as its own coverage or gap records. Opportunities are alternatives, not a
checklist: one detection that reliably catches a procedure is full coverage,
and building every published opportunity would mostly add cost and duplicate
alerts. Which ones to implement, and how many, is the engineer's call.

A private library can hold opportunity records too — for procedures in a
private TRR library, which a public library cannot reference, or for detection
paths that rely on telemetry only that organization has. It also gives an
engineer an honest record for "assessed, and buildable, but not yet built,"
which is neither a gap nor an absence of assessment.

Opportunity records have their own sections — Overview, Opportunity,
Considerations, References — and their own schema,
`.tiredize/schema-opportunity.yaml`. `tools/lint_records.py` lints each record
against the schema for its type.

### Core fields and provider details

Every record carries the same core fields: ID, Type, Status, Contributors,
Platforms, Tactics, Techniques, Procedures, and — for coverage — Provider.

Everything below Provider is provider-specific. Those fields differ by provider
and the core tooling makes no attempt to understand them: the indexer nests them
under `provider_details` so that every coverage record has the same shape in the
index no matter which provider supplied it.

```json
{
  "id": "PCR0010",
  "type": "Coverage",
  "provider": "Anvilogic",
  "provider_details": {
    "avl_rule": "AVL_R267667",
    "schedule": "1h",
    "severity": "High"
  }
}
```

This is what makes downstream validation possible. A validation system needs the
provider's own identifiers to check a piece of coverage against the system that
provides it, and `provider_details` is where those live.

## Identifiers

Records are identified as `<PREFIX><NNNN>` — `PCR0034` in a repository
configured with `id_prefix: "PCR"`. Folder names use the lowercase form.

Newly created records use a `CR000N` placeholder instead, in every deployment
regardless of prefix, so that templates and documentation need no per-instance
templating. The merge automation assigns the real ID and renames the folder and
its contents in one step. A contributor never picks a number.

The placeholder runs `CR0000` through `CR0009` because one create action can
scaffold several related records at once — a provider integration may need a
primary record plus companions. Assigned IDs therefore start at 0010.

## Repository layout

```text
root
|_ local/                   everything specific to THIS instance
|  |_ config.json           repository configuration
|  |_ templates/            instance templates, override core by filename
|  \_ integrations/<name>/  provider integrations, including hooks.py
|_ .tiredize/
|  |_ schema.yaml           expected section structure
|  |_ rules.yaml            style rules, run on pull requests
|  |_ rules-links.yaml      link checking, run weekly
|  \_ requirements.txt      pinned Tiredize version
|_ records/
|  \_ <prefix><nnnn>/
|     \_ README.md          the record itself
|_ templates/               base record templates
|_ tools/                   indexer, validator, record creation
\_ docs/                    style guide, design, deployment
```

**The template contains nothing under `local/` except documentation and an
example config.** That is the invariant the whole design rests on: everything an
instance owns lives under `local/`, so pulling updates from upstream can never
conflict with instance content.

## Configuration

`local/config.json` holds everything specific to a deployment: the ID prefix,
the platform map, the core fields, and the providers.

```json
{
  "schema": 1,
  "id_prefix": "PCR",
  "platforms": {
    "Windows": "win",
    "Linux": "lin"
  },
  "core_fields": {
    "Title": {
      "type": "single",
      "required": true
    },
    "Status": {
      "type": "single",
      "required": true,
      "values": [
        "Active",
        "Retired"
      ]
    },
    "Techniques": {
      "type": "list",
      "required": false
    }
  },
  "providers": {
    "Preventative": {
      "template": "coverage-template.md",
      "fields": {}
    },
    "Anvilogic": {
      "template": "avl-detection-template.md",
      "fields": {
        "Schedule": {
          "type": "single",
          "required": true,
          "values": [
            "1h",
            "24h"
          ]
        },
        "Lookback": {
          "type": "single",
          "required": true,
          "values": [
            "Standard"
          ],
          "pattern": "^[0-9]{1,3}[mhd]$"
        }
      }
    }
  }
}
```

Copy `local/config.example.json` to `local/config.json` to start. The example
ships `id_prefix` as `XXXX`, which every tool rejects, so an unconfigured
instance fails loudly rather than quietly producing records under a placeholder
identifier.

`core_fields` and a provider's `fields` are the contract a record must
meet. Core fields apply to every
record; a provider's fields layer on top for the records that name it. Each
declares its `type` (`single` or `list`) and may constrain the value with
`required`, `values`, `pattern`, or `values` and `pattern` together, meaning
either is acceptable.

Core enforces all of it, so declaring a field is the whole job — a provider
needs a `validate_record` hook only for a rule the declarations cannot state.

A declared field must have a row in the metadata table. An empty value is
allowed unless `required`; a missing row is not. Keeping those apart is what
catches a record drifting from its template, where the field would otherwise
disappear without trace.

## Templates

Core ships base templates in `templates/`. An instance's own templates go in
`local/templates/` and win on filename collision, so an instance can replace a
base template without editing it and without conflicting on merge.

A record's template is chosen by provider, not by type: gap records use the gap
template, and coverage records use their provider's.

## Provider integrations

An integration lives at `local/integrations/<provider-slug>/`. The Provider
metadata value *is* the dispatch key — coverage supplied by `Anvilogic` looks
for `local/integrations/anvilogic/hooks.py`. There is no registry to maintain:
adding an integration is adding a directory.

Four hooks are called if present, and nothing happens if they are not:

| Hook | Called when | May |
|------|-------------|-----|
| `validate_record` | every PR, and every full validation run | report errors. **Must be pure.** Rarely needed — declare fields in config instead |
| `on_record_created` | a record is scaffolded | create provider objects, return companion record paths |
| `on_record_changed` | a PR touched a record, after validation passed | write to the working tree, call the platform |
| `on_record_merged` | a record is merged, has its ID, and is indexed | promote, deploy, undeploy |

`validate_record` runs inside the standard validation pass, so a provider's
value checks happen on every pull request and on an offline full-corpus run.
That is why it must have no side effects: someone will run
`python3 tools/index.py validate` over every record, and it should not touch
anything.

Every hook receives a **context**. `context.is_new` is the important one: it
says whether core has just assigned this record its ID, which is how a
provider tells "never deployed" from "already live" without inferring it from
the ID. An earlier version of this design left providers to guess, and the
guess only worked because of the order two workflow steps happened to run in.

A repository with no integrations runs the same code path with every hook
absent. Core never imports an integration and never needs to know one exists.

### Both directions of detection-as-code

`on_record_changed` may write to the working tree, and core commits whatever
it changes back to the pull request branch. That supports two shapes with the
same mechanism:

- **Pure detection-as-code** -- the repository is authoritative for the rule
  logic too, so the hook reads it from the record and pushes it to the
  platform.
- **Compromise** -- the platform owns the authoring surface for the logic and
  nothing else, so the hook pulls the current logic from the platform and
  writes it into the record, where the pull request captures it for review.

Core does not know or care which a provider chose. It is the same hook, run in
the opposite direction.

Whether anything is *deployed* at this point is also the provider's choice.
Some teams want a new detection running in a test mode as soon as the pull
request opens, so alert volume and filtering can be assessed before it reaches
an analyst. Others want nothing to happen until merge.

### Tasks

Some provider work belongs to no record's lifecycle: reconciling the
platform's state against this repository, audits, bulk operations. Those are
**tasks**, defined in `local/integrations/<slug>/tasks.py` and invoked by core's
generic runner rather than by an event:

```bash
python3 tools/run_provider_task.py Anvilogic reconcile
```

Core resolves the provider, loads the configuration and the index, and calls
the named function. Adding a task needs no change to core.

## Validation

Two independent checks run against every record, answering different questions.

**Structural validation** asks whether the document is well-formed: correct
sections in the correct order, formatting and line-length conventions observed.
This is handled by [Tiredize], a schema-driven markdown linter configured by
`.tiredize/schema.yaml` and `.tiredize/rules.yaml`.

**Semantic validation** asks whether the content is legal for *this* repository,
which requires knowledge a generic linter does not have. It runs as a mode of
the indexer, reusing the same parser that builds the index so the two can never
disagree. Run it against named files or, with no arguments, against every record
in the repository:

```bash
python3 tools/index.py validate
```

It checks that the ID matches the configured prefix and its folder, the type is
configured, coverage records name a configured provider and gap records name
none, every declared field has a row and a legal value, platforms are known,
referenced files exist, and no other record claims the same ID.

### The index envelope

`index.json` is a document, not a bare array:

```json
{
  "schema": 2,
  "generated": "2026-09-22T14:03:00Z",
  "platforms": { "Active Directory": "ad", "Windows": "win" },
  "records": [ ... ]
}
```

`schema` lets a consumer decide whether it understands the file rather than
inferring that from its shape. `generated` is when the index was last written,
so a dashboard can show real freshness instead of the time it happened to
fetch. `platforms` is copied verbatim from the repository configuration, which
means a consumer can resolve a record's platform short code without fetching
anything else -- and because validation rejects a record naming an
unconfigured platform, every platform appearing in `records` is guaranteed to
be in the map.

The indexer still reads a bare array, so a repository written by an earlier
version reindexes without a migration step.

## Automation

Three workflows do the work.

**On pull request**, two workflows run, and the split between them is the
point.

`lint.yml` is read-only. It lints changed records and validates them -- core
checks plus each provider's own `validate_record`, which is pure -- and writes
nothing. Because it changes nothing, it is safe to run on every commit a pull
request ever has, which is what makes it a trustworthy required status check:
it always reports on the current head.

`provider-sync.yml` does the writing. It runs `index.py review`, which validates
every record first and refuses to call any provider unless all of them passed;
only then does it run `on_record_changed`. Keeping that order inside one command
is deliberate: expressed as workflow step order, nothing would stop the provider
running after validation had failed, whereas as one mode, "nothing reaches a
provider unless validation passed" is a property of the code.

Anything a provider writes is committed back to the pull request branch **using
the GitHub App token**. That choice carries most of the design:

- **App pushes trigger workflows.** `lint.yml` runs on the new head, so the
  pull request's status always describes its current commit. A push made with
  the workflow's own token triggers nothing, which left the required check
  reporting on an older commit and the pull request unmergeable -- or, in some
  configurations, triggered a run held for manual approval.
- **No commit carries `[skip ci]`.** A squash merge concatenates every commit
  message on the branch into one, so a `[skip ci]` anywhere in a pull request
  reaches `main` and suppresses the push trigger that runs the reindex.

Because its own commit triggers it again, `provider-sync.yml` checks who wrote
the head commit and does nothing if it did. It matches on the commit author
rather than the pushing account, since an App's account name differs in every
deployment while the author is set by the workflow itself.

**On any push to `main`**, new records are assigned identifiers, folders and
files are renamed, the index is regenerated, provider hooks fire, and the result
is committed back to `main`.

The push itself is the trigger rather than a pull request closing. GitHub does
not reliably queue the merge commit job for closed pull requests, and a merge
that bypasses branch protection can leave a pull-request-triggered workflow
unfired even though `main` did receive the commits. A push always fires, however
the change arrived.

Two consequences follow. The job runs one at a time (`concurrency`), because two
records merged close together would otherwise read the same index and be
assigned the same identifier. And its own commit is tagged `[skip ci]` and
skipped on the next run, because a GitHub App token — unlike the token GitHub
issues to a workflow — does trigger workflows. That commit is the only place
`[skip ci]` is used: it goes straight to `main`, so unlike a commit on a pull
request branch it can never be folded into a squash merge.

The tag has one consequence for anything downstream. `[skip ci]` suppresses
every push-triggered workflow for that commit, and that commit is the one
carrying the rebuilt index. Automation that should react to a new index —
publishing it to Insomnia, say — must therefore trigger on this workflow
completing (`workflow_run`), not on push: triggered on push, it would see only
the merge commit and its stale index.

**Weekly**, external links in records are checked and a single tracking issue is
kept up to date with any that fail. This is deliberately not a pull request
check: link rot is a maintenance concern, and a record should not fail review
because a third-party site was down that morning.

A fourth workflow, **Create New Record**, is run manually to scaffold a record
on a working branch. It is the one workflow instances are expected to override,
because workflow inputs are static YAML and an integration cannot contribute a
dropdown at runtime.

## How the template is published

The upstream repository serves two purposes from two branches:

| Branch | Holds |
|--------|-------|
| `template` | The template: tooling, workflows, documentation, and templates. No instance content. |
| `main` | The public coverage library: the template, plus its configuration and published opportunity records. |

`main` is simply an instance whose upstream is the `template` branch of the same
repository. The rule that makes every instance mergeable — the template ships
nothing an instance owns — is what keeps merges from `template` into `main`
free of conflicts. Instance content means `local/` (beyond its scaffolding),
`records/`, `index.json`, and `.github/README.md`, which GitHub shows in
preference to the template-owned root README.

The rules for maintaining it:

- **Changes flow one way, `template` into `main`.** Merging `main` into
  `template` would pour the public instance's configuration and records into
  every future instance.
- **Tooling changes land on `template` first.** Pull requests into `main` may
  change only instance content; everything else arrives by merging `template`
  in.
- **`branch-guard.yml` enforces both**, and should be a required check on both
  branches. In an organization's own instance it does nothing: an instance is
  cloned from `template` alone and renamed to `main`, so no pull request ever
  targets a `template` branch, and the check on `main` runs only where one
  exists.
- **Merge `template` into `main` with a merge commit — never squash or
  rebase.** A squash merge brings the template's changes across without
  recording that its commits were merged, so the next sync tries to apply them
  again and conflicts; a rebase rewrites them. Allow merge commits in the
  repository settings, and choose "Create a merge commit" for the sync pull
  request.
- **Tag template releases** — `template-v1.4.0` — so instances can merge a known
  version rather than whatever is current.
- **Leave GitHub's "Template repository" setting off.** "Use this template"
  copies the default branch, which here is the public instance.

## Third-party actions

The workflows use only GitHub-owned actions. Changed-file detection is done with
`git diff` in a run step rather than a third-party action, specifically so that
organizations restricting which actions may run can use this template
unmodified. Tiredize installs from pip and needs no allowlist entry.

Instances running self-hosted runners will need to change `runs-on` from
`ubuntu-latest` in each workflow.

[Tiredize]: https://github.com/tired-labs/tiredize
