# Coverage Records Library

> This is the TIRED Labs coverage records template. Deployed libraries — the
> public library of detection opportunities, and any private library an
> organization runs — are instances of it. See the [Deployment Guide].

> The template lives on this repository's **`template` branch**; `main` holds
> the public instance. To deploy your own, clone the `template` branch — see
> [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Overview

This repository is the source of record for an organization's known attack
technique coverage. It holds two kinds of record:

- **Coverage records** describe coverage that exists, and name the **provider**
  supplying it. Coverage that is not an active detection — OS hardening, network
  segmentation — uses the provider `Preventative`.
- **Gap records** describe coverage that does not exist.

Detections are not a separate type. A detection is a coverage record whose
provider happens to be a detection platform.

Records are written in Markdown under `records/`, one folder per record, and
indexed into `index.json` for [Insomnia] to read alongside the technique
research it maps to.

## A note on visibility

A coverage record library is a map of what an organization can and cannot
detect. Deployments are private by definition, there is no public contribution
flow, and this repository ships no example records.

## Working with records

Run the **Create New Record** workflow from the Actions tab to scaffold a record
on a working branch, fill it in, and open a pull request. Structure, style, and
metadata are all checked automatically; see the [Style Guide] for the
conventions, and check your work locally before opening the PR:

```bash
pip install -r .tiredize/requirements.txt

python3 tools/lint_records.py \
  records/<id>/README.md
python3 tools/index.py validate -f records/<id>/README.md
```

An ID is assigned automatically when your record is merged — you never pick one.

## Configuration

Everything specific to this deployment lives in [`local/`](./local/README.md):
configuration, templates, and provider integrations. Core tooling and workflows
come from the template and should not be edited here.

## Documentation

- [Repository Design] — how the pieces fit together
- [Deployment Guide] — standing up a new library
- [Style Guide] — writing well-formatted records

[Deployment Guide]: ./docs/DEPLOYMENT.md
[Repository Design]: ./docs/DESIGN.md
[Style Guide]: ./docs/STYLE-GUIDE.md
[Insomnia]: https://github.com/tired-labs
