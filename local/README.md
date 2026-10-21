# Instance-specific content

Everything in this directory belongs to **this deployment** of the coverage
records template. The template itself ships nothing here except this file and
`config.example.json`.

That is the invariant the design rests on: because upstream never places content
under `local/`, pulling template updates can never conflict with anything you
own.

## What goes here

| Path | Holds |
|------|-------|
| `config.json` | This repository's configuration. Copy `config.example.json` to start. |
| `templates/` | Your record templates. A file here overrides a core template of the same name. |
| `integrations/<provider>/` | Provider integrations, including `hooks.py` and any vendor libraries they need. |
| `pull_request_template.md` | Your canonical PR template; copy it to `.github/` where GitHub reads it. |

Anything else specific to your organization belongs here too — field contracts
that apply across providers, review guidance for an AI first-pass reviewer,
runbooks. If it describes how *your* organization works rather than how a
coverage record library works, it goes in `local/`.

## Adding a provider integration

`integrations/example-provider/hooks.example.py` is a commented starting point
covering all four hooks; `tasks.example.py` covers scheduled work such as
reconciliation; `requirements.example.txt` covers dependencies. Copy them to
`integrations/<provider-slug>/` as `hooks.py`, `tasks.py`, and
`requirements.txt`, and edit.

Dependencies are installed automatically — core runs
`tools/install_provider_deps.py` in every workflow that might call a hook, so
adding a provider never means editing a workflow. The slug is the
Provider value lowercased with runs of non-alphanumeric characters replaced by
hyphens, so `Acme Cloud SIEM` becomes `acme-cloud-siem`.

There is nothing to register: creating the directory is what wires it up. Both
hooks are optional, and a provider with no integration at all works normally --
its records are created, validated, and indexed as usual, with no side effects.

## Credentials

Dependencies install themselves; credentials do not. GitHub will not let a
workflow enumerate `secrets`, so core cannot forward what it cannot name.

Each hook-calling step in `provider-sync.yml`, `merge.yml`, and `create-record.yml`
carries an `env:` block with a marker comment. Add your providers' secrets
there. Those three blocks are an override point — small, but they live in
files core otherwise owns, so re-add them when you port an upstream change.

## What does not go here

Core tooling, workflows, schemas, and base templates. If you find yourself
wanting to change one of those, consider whether the change belongs upstream
instead: a fix made in the template reaches every deployment, while a local edit
to a core file is exactly the merge conflict this directory exists to prevent.

See [../docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md) for setup, and
[../docs/DESIGN.md](../docs/DESIGN.md) for how integrations attach.
