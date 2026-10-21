"""EXAMPLE provider tasks. Copy, rename, and edit.

Named `tasks.example.py` so that it is never loaded -- core looks for exactly
`tasks.py` in the same directory as your `hooks.py`.

Hooks cover a record's lifecycle: created, changed, merged. Some provider work
does not belong to any record's lifecycle at all:

  * reconciling your platform's state against this repository, on a schedule,
    to catch changes made outside the pull request workflow
  * auditing, reporting, one-off bulk operations
  * anything you would otherwise write a bespoke script and workflow for

Those are tasks. Core resolves the provider, loads the configuration and the
index, and calls the function you name:

    python3 tools/run_provider_task.py Anvilogic reconcile
    python3 tools/run_provider_task.py Anvilogic reconcile -o '{"dry_run": true}'

Adding a task needs no change to core. Schedule it with a workflow of your own
under `.github/workflows/`.
"""

##############################################################################
################################## IMPORTS ###################################
##############################################################################
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), "tools"))
import records_lib  # noqa: E402


##############################################################################
#################################### TASKS ###################################
##############################################################################
def reconcile(files, config, context, index):
    """Compare the provider's state against this repository.

    Every task takes the same four arguments:

        files    list of paths passed with -f, or None
        config   the parsed local/config.json
        context  a HookContext. context.options holds whatever was passed
                 with -o as JSON; context.provider is the provider name
        index    the parsed index.json

    Return None or 0 for success, False or a non-zero int to fail the run.
    Raising works too -- core reports it and exits non-zero.

    A scheduled task is usually reporting rather than fixing: it is safer to
    open an issue describing the drift than to silently change either side.
    Take `dry_run` seriously if you do decide to reconcile automatically.
    """
    dry_run = context.options.get('dry_run', False)

    # The index tells you what this repository believes is deployed.
    ours = {
        entry['id']: entry.get('provider_details', {})
        for entry in index
        if entry.get('provider') == context.provider
    }
    print(f"{len(ours)} record(s) in this repository for {context.provider}.")

    # Fetch the equivalent from your platform and compare.
    #
    #     theirs = my_platform.list_rules()
    #     missing = set(theirs) - {d.get('rule_id') for d in ours.values()}
    #     if missing:
    #         print(f"{len(missing)} rule(s) on the platform have no record.")

    if dry_run:
        print("Dry run; reporting only.")

    return 0


def audit(files, config, context, index):
    """A second task, to show that a provider may define as many as it needs.

    Core looks up the function by the name given on the command line, so
    there is nothing to register.
    """
    records = list(
        records_lib.iter_provider_records(
            files or [], context.provider, config
        )
    )
    print(f"Audited {len(records)} record(s).")
    return 0
