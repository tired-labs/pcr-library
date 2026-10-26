# Deployment Guide

This guide covers standing up your own coverage record library from this
template, and keeping it current afterward. If you want to understand how the
repository is put together first, read the [Repository Design] document.

**Deploy this into a private repository.** A coverage record library is a map of
what your organization can and cannot detect. Unlike a TRR library, there is no
public deployment of this template and no public contribution flow — the records
are inherently sensitive defensive information.

You will need permission to create a private repository and a GitHub App in your
organization, and to configure branch protection.

## 1. Create the repository

The upstream repository has two branches. `main` holds the public instance —
its configuration and published content. `template` holds the template itself,
and is what you build from.

Do **not** use GitHub's "Use this template" button, and do not use the fork
button. The template button copies the default branch — the public instance's
content — and produces a repository with no shared history, which permanently
removes your ability to pull in later tooling fixes. The fork button cannot
produce a private repository from a public one.

Clone the `template` branch alone and push it to your own private repository as
`main`, keeping the upstream configured as `upstream`:

```bash
git clone --single-branch --branch template https://github.com/<upstream-org>/<upstream-coverage-repo>.git my-coverage-library
cd my-coverage-library
git branch -m template main

# Point 'origin' at your new private repository
git remote rename origin upstream
git remote add origin https://github.com/<your-org>/my-coverage-library.git
git push -u origin main
```

`--single-branch` means you receive only the template's history, never the
public instance's. The `upstream` remote is what makes updates possible later.
Do not remove it.

To give your repository its own landing page, put a README at
`.github/README.md`. GitHub shows that in preference to the root `README.md`,
which describes the template and belongs to it — so your page never conflicts
with an update.

## 2. Configure the repository

Copy the example configuration and edit it:

```bash
cp local/config.example.json local/config.json
```

**`id_prefix`** is what distinguishes your records. It must be 2-8 characters,
uppercase letters and digits only, starting with a letter. The example ships
`XXXX`, which every tool rejects, so nothing will run until you change it.

**`platforms`** maps each platform's display name to the folder code its
records live under. Adjust to match how your organization describes its estate.

**`core_fields`** declares the metadata every record carries. Each entry needs a
`type` — `single` for one value, `list` for a comma-separated one — and may
set `required`, `values`, and `pattern`:

```json
"core_fields": {
  "Title":        { "type": "single", "required": true },
  "Status":       { "type": "single", "required": true,
                    "values": ["Active", "Retired"] },
  "Contributors": { "type": "list", "required": true },
  "Platforms":    { "type": "list", "required": true },
  "Tactics":      { "type": "list", "required": false }
}
```

**`providers`** names the systems that supply coverage. Each has a template
and its own `fields` block, layered on top of the core fields for records that
name it:

```json
"providers": {
  "Preventative": { "template": "coverage-template.md", "fields": {} },
  "Anvilogic": {
    "template": "avl-detection-template.md",
    "fields": {
      "Schedule": { "type": "single", "required": true,
                    "values": ["15m", "30m", "1h", "4h", "12h", "24h"] },
      "Lookback": { "type": "single", "required": true,
                    "values": ["Standard"],
                    "pattern": "^[0-9]{1,3}[mhd]$" },
      "AVL Rule": { "type": "single", "required": true }
    }
  }
}
```

> [!NOTE]
>
> The `Preventative` provider is for identifying coverage that is not an active
> detection: OS hardening, network segmentation, and anything else that reduces
> exposure without producing an alert. You should not modify or remove it.

### How fields are checked

| Key | Effect |
|---|---|
| `type` | Required. `single` or `list`. A `list` is split on commas and every item is checked separately |
| `required` | `true` means the value must not be empty. Defaults to `false` |
| `values` | The value must be one of these |
| `pattern` | The value must match this regular expression |

`values` and `pattern` together mean **either** is acceptable — which is how
`Lookback` accepts the word `Standard` or a duration like `30d`.

Comparison is case-insensitive, so `High` and `high` both pass and the record
keeps whatever the author wrote.

Field names are the human-readable ones from the record's metadata table, so
`"AVL Rule"` matches `| AVL Rule |`. Core transforms them internally, which is
why `index.json` and hook code see `avl_rule`.

**Every declared field must have a row in the metadata table.** A blank value
is allowed unless `required` is set, but a missing row is an error — that
distinction is what catches a record drifting away from its template, where the
field would otherwise vanish silently.

This is the whole validation surface for most providers. A `validate_record`
hook is only needed for something these declarations cannot state, such as a
rule relating two fields to each other.

## 3. Everything of yours lives in `local/`

The template contains nothing under `local/` but this documentation and the
example config. That is deliberate: it means upstream updates can never conflict
with anything you own.

| Path | Holds |
| --- | --- |
| `local/config.json` | your configuration |
| `local/templates/` | your record templates; override core by filename |
| `local/integrations/<provider>/` | provider integrations, including `hooks.py` |
| `local/pull_request_template.md` | see below |
| Anything else instance-specific | field contracts, review guidance, runbooks |

Two files cannot be layered and must be instance-owned copies:

- **`.github/pull_request_template.md`** — GitHub reads exactly one file at that
  path, so keep your canonical copy in `local/` and place the live one at
  `.github/`. The template ships none.
- **`.github/workflows/create-record.yml`** — see step 6.

## 4. Add a provider integration (optional)

If a provider needs to do something when a record is created or merged, add
`local/integrations/<provider-slug>/hooks.py`. The slug is the Provider value
lowercased with non-alphanumerics replaced by hyphens, so `Anvilogic` becomes
`anvilogic`.

`local/integrations/example-provider/hooks.example.py` is a commented starting
point covering all four hooks:

| Hook | Purpose |
| --- | --- |
| `validate_record` | a hook to implement checks that the `config.json` cannot express. Rarely needed |
| `on_record_created` | create platform objects for a new record |
| `on_record_changed` | sync during review; may deploy, may write to the record |
| `on_record_merged` | promote, deploy, or undeploy after merge |

All are optional. Define only what you need; core skips whatever is absent, and
a repository with no integrations never notices.

Read `context.is_new` rather than inferring from the ID whether a record has
been deployed before — core knows, and says so.

If a provider needs work that is not part of any record's lifecycle —
reconciliation, audits, bulk operations — put it in `tasks.py` alongside
`hooks.py` and invoke it with core's runner:

```bash
python3 tools/run_provider_task.py <Provider> <task>
```

`tasks.example.py` shows the shape. Schedule it with a workflow of your own.

Vendor libraries that an integration depends on belong under the same directory
— `local/integrations/anvilogic/avl/`, say — and should be treated as
vendor-provided code: pinned to a version, regenerated rather than patched, and
recorded in a `PROVENANCE.md` alongside. Declare the package in
`local/integrations/<slug>/requirements.txt` and core installs it
automatically — every workflow that might call a hook runs
`tools/install_provider_deps.py`, so no workflow needs editing.

### Giving an integration its credentials

Dependencies are discovered automatically; credentials cannot be. GitHub does
not let a workflow enumerate `secrets`, so core has no way to forward
credentials whose names it does not know.

Each hook-calling step therefore carries an `env:` block with a marked
override point. Core ships it containing only `REPO_URL`; you add your
providers' secrets to it:

```yaml
      env:
        REPO_URL: ${{ github.server_url }}/${{ github.repository }}/blob/main/
        AVL_API_KEY: ${{ secrets.AVL_API_KEY }}
        AVL_API_URL: "https://secure.anvilogic.com"
```

Three files need this, and they are **the third known override point** after
`create-record.yml` and the pull request template:

| File | Step |
|------|------|
| `.github/workflows/provider-sync.yml` | Run provider hooks for changed records |
| `.github/workflows/merge.yml` | Update modified records using indexer |
| `.github/workflows/create-record.yml` | Create the record |

Unlike the other override points, these are small additions inside otherwise
upstream-owned files. Expect to re-add them when you merge an upstream change
that touches those steps — the marker comment is there to make them easy to
spot in a conflict.

Most vendor SDKs read their own credentials straight from the environment, so
an integration usually does not reference the secret at all: it is enough that
the variable is set in the step that calls the hook.

## 5. Install and pin Tiredize

Structural linting is done by [Tiredize], a schema-driven markdown linter. It is
a Python package rather than a GitHub Action, so it installs with `pip` and is
unaffected by any restriction your organization places on which actions may run.

Tiredize is not yet published to PyPI, so despite what its README says,
`pip install tiredize` will not work. The template pins a specific commit in
`.tiredize/requirements.txt`:

```bash
pip install -r .tiredize/requirements.txt
```

Pinning matters. Tiredize is pre-1.0 and has no release tags, so tracking its
`main` branch means your linting rules can change without you touching your
repository — and a rule that tightens between two pull requests will fail
contributions that would have passed the day before.

### The definition files

| File | Purpose |
| --- | --- |
| `.tiredize/schema.yaml` | Section structure of coverage and gap records |
| `.tiredize/schema-opportunity.yaml` | Section structure of opportunity records |
| `.tiredize/rules.yaml` | Style rules for pull requests: line length, whitespace |
| `.tiredize/rules-links.yaml` | Link checking, run weekly |

All are yours to adjust. Test any change against your whole corpus before
committing it, since a schema stricter than your existing records will reject
work already merged:

```bash
python3 tools/lint_records.py $(find records templates local/templates -name '*.md')
```

Use `tools/lint_records.py` rather than calling `tiredize` directly. Opportunity
records have different sections from coverage and gap records, and Tiredize
applies one schema per run, so the script lints each record against the schema
for its type.

Note what these files deliberately do *not* cover: record types, platforms,
providers, and provider field contracts are checked by the validator instead,
because they depend on `local/config.json` and a generic linter cannot know
them. If you find yourself wanting to encode configuration values in
`schema.yaml`, that check belongs in the validator.

### Link checking

Link checking is split into its own rules file and runs weekly rather than on
pull requests, because link rot is a maintenance problem and a record should not
fail review because a third-party site was down. The workflow maintains a single
tracking issue labelled `link-check`, rewriting its body each run and closing it
once everything resolves.

Sites returning 403 or 429 to automated requests are treated as reachable, since
bot-blocking cannot be told apart from a real permissions wall. If you have
internal hosts a runner cannot resolve, add them to `exclude` in
`rules-links.yaml` rather than disabling the check.

## 6. Own your create-record workflow

Workflow inputs are static YAML, so an integration cannot contribute a dropdown
at runtime. If your providers need extra inputs — an Anvilogic domain, a data
category — add them to the `inputs` block of
`.github/workflows/create-record.yml` and keep your own copy.

To keep that divergence cheap, the workflow forwards **all** of its inputs to
`create_record.py` as JSON, which passes them to the provider's
`on_record_created` hook in `context.options`. The run step therefore never
changes when you add inputs, and porting an upstream fix means copying the steps
and keeping your own inputs block.

The workflow's `branch_name` input names the branch the record is created on;
left blank, it is `record/<UTC timestamp>`. The name is checked before anything
is created — an invalid name, or one that already exists, fails the run rather
than being rewritten — and the hook receives it in `context.branch`, so a
provider can label what it creates with the branch that holds its record.

## 7. Set up the GitHub App

Two workflows push commits, and both use this App.

When a record is merged, `merge.yml` assigns its ID, renames its files,
regenerates the index, runs provider hooks, and pushes the result to `main`. If
`main` is protected — and it should be — that push needs an identity permitted
to make it.

During review, `provider-sync.yml` commits anything a provider wrote back to the
pull request branch. It uses the App so that the push triggers the checks again:
a push made with the workflow's own token would leave the required check
reporting on an older commit, and the pull request could not be merged.

The token GitHub issues to a workflow cannot do this. It cannot bypass branch
protection, and the identity behind it cannot be added to a bypass list, because
GitHub does not treat it as a bypassable actor. A GitHub App can be.

1. Create a GitHub App under your organization
   (**Settings → Developer settings → GitHub Apps → New GitHub App**).
   - Uncheck **Webhook → Active**; the app receives no events.
   - Under **Repository permissions**, grant **Contents: Read and write**.
2. Generate a private key and download the `.pem` file.
3. Install the App on your library repository.
4. Add two secrets under **Settings → Secrets and variables → Actions**:
   - `GH_APP_CLIENT_ID` — the App's **Client ID**, shown on its settings page
   - `GH_APP_PRIVATE_KEY` — the full contents of the `.pem` file

## 8. Configure branch protection

Under **Settings → Rules → Rulesets**, create a ruleset targeting `main` that
requires a pull request before merging, and requires these status checks:

| Check | Why it must pass |
|-------|------------------|
| `lint_and_validate` | The records are well-formed and legal for this repository |
| `provider_sync` | Providers have finished, and anything they wrote is committed |

Requiring `provider_sync` stops a pull request being merged while a provider is
still deploying or before its synced files reach the branch. On the workflow's
own commit it skips itself and reports success, so it never blocks the second
round of checks. Neither workflow uses a path filter, deliberately: a required
check whose workflow is filtered out never reports, and the pull request waits
on it forever.

Then add your GitHub App to the ruleset's **Bypass list**.

Without the bypass entry, everything works until the first merge, at which point
the indexing job fails on the push.

## 9. Check runners and actions

The workflows use only GitHub-owned actions (`actions/checkout`,
`actions/setup-python`, `actions/create-github-app-token`), so an organization
restricting the `actions/*` namespace can use them unmodified.

They also specify `runs-on: ubuntu-latest`. If your organization requires
self-hosted runners, change that label in all four workflows.

## 10. Verify the setup

From the repository root:

```bash
# Structural checks, each record against the schema for its type
python3 tools/lint_records.py \
  $(find records templates local/templates -name '*.md' 2>/dev/null)

# Semantic checks against your configuration
python3 tools/index.py validate
```

Both should pass. If the validator reports that `id_prefix` is still `XXXX`,
step 2 is incomplete.

Then run **Create New Record** from the Actions tab, open a pull request from
the branch it creates, confirm the checks run, and merge it. You should see the
record renamed from its `CR000N` placeholder to your prefix with the next
available number, and an indexing commit pushed to `main` by the App. If that
commit is rejected, revisit step 8.

## Keeping your instance current

Tooling is copied into your repository rather than referenced from a shared
location, so improvements reach you only when you pull them in — always from
the upstream's `template` branch:

```bash
git fetch upstream template
git merge upstream/template
```

**Never merge `upstream/main`.** That is the public instance, and merging it
would pour its configuration and content into your repository.

To take a specific release rather than the latest template, merge its tag
instead — `git merge template-v1.4.0`, say, after `git fetch upstream --tags`.

Everything you own lives in `local/`, `records/`, `index.json`, and
`.github/README.md`, and the template ships none of it. Conflicts are limited
to the workflows you deliberately keep copies of — `create-record.yml`,
`provider-sync.yml`, and `merge.yml`, when they carry your provider
credentials — and the pull request template.

Merge periodically rather than waiting for something to break. Validation gains
checks over time, and a library that has not merged in a long while will
accumulate records that current rules would reject. After a merge, run a full
validation pass:

```bash
python3 tools/index.py validate
```

## Connecting to Insomnia

Your repository publishes `index.json` at its root, and that is the only file a
consumer needs. It holds no Insomnia configuration and needs no awareness of
any other repository.

A coverage repository is private, and a browser cannot fetch a private
repository, so Insomnia reads your index from its own `data/` folder. In
Insomnia's `local/config.json`:

```json
{ "Name": "ACME Coverage", "Type": "coverage",
  "Repo": "https://github.example.com/acme/coverage-records",
  "Load": "local" }
```

`Repo` tells Insomnia where to fetch from, and links each record card back to
the record here — viewers open those links with their own credentials.

Your index reaches Insomnia's `data/` in one of two ways, and they combine
well:

- **Pulled** by Insomnia's weekly sync. Install Insomnia's GitHub App on this
  repository with **Contents: Read**.
- **Pushed** by a workflow in this repository, within seconds of each merge.

### Publishing on merge

Add `.github/workflows/publish-to-insomnia.yml`:

```yaml
name: Publish index to Insomnia

on:
  workflow_run:
    workflows: ["Index new record on merge"]
    types: [completed]

jobs:
  publish-to-insomnia:
    if: github.event.workflow_run.conclusion == 'success'
    uses: <your-org>/<your-insomnia>/.github/workflows/push-to-insomnia.yml@main
    with:
      source-name: "ACME Coverage"     # must match Name in Insomnia's config
      insomnia-repo: "<your-org>/<your-insomnia>"
    secrets:
      client-id: ${{ secrets.GH_APP_CLIENT_ID }}
      private-key: ${{ secrets.GH_APP_PRIVATE_KEY }}
```

**Trigger it on `merge.yml` finishing, not on push to `main`.** After a merge,
`merge.yml` rebuilds `index.json` in a commit of its own, tagged `[skip ci]` so
it does not trigger `merge.yml` again. But `[skip ci]` suppresses *every*
push-triggered workflow for that commit. A publish workflow triggered `on: push`
would run only on the merge commit — whose index is still the old one — and
skip the commit carrying the new one, leaving Insomnia one merge behind with
every run reporting success. Triggered on `workflow_run`, it runs once, after
the rebuild, against the latest `main`.

The same applies to anything else that should react to a new index: trigger it
on `merge.yml` completing. `Index new record on merge` is `merge.yml`'s name; if
you rename it, update the trigger too, because a `workflow_run` that names no
existing workflow never fires, and nothing reports it.

The `source-name` must match the source's `Name` in Insomnia's configuration
exactly, and that source must be `Load: "local"`. The App needs **Contents:
Read** here and **Contents: Read and write** on Insomnia.

[Repository Design]: ./DESIGN.md
[Tiredize]: https://github.com/tired-labs/tiredize
