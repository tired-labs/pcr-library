"""EXAMPLE provider integration. Copy, rename, and edit.

This file is named `hooks.example.py` so that it is never loaded -- core looks
for exactly `hooks.py`. To turn it into a real integration:

  1. Work out your provider's slug. Core lowercases the Provider value from a
     record's metadata and replaces runs of non-alphanumeric characters with
     hyphens, so `Acme Cloud SIEM` becomes `acme-cloud-siem`.
  2. Create `local/integrations/<slug>/` and copy this file in as `hooks.py`.
  3. Add the provider to `local/config.json` under `providers`, with its
     template and a `fields` block declaring each metadata field it needs.
     Core enforces those declarations, so most providers need no
     validate_record hook at all.
  4. Delete whichever hooks you do not need. All are optional.

Four hooks are available:

  validate_record     every PR and every full validation run. MUST be pure --
                      no writes, no API calls. Return a list of errors.
                      Rarely needed: declare fields in config instead.
  on_record_created   a record was scaffolded.
  on_record_changed   a PR touched a record, and validation passed. May write
                      to the working tree and may call your platform.
  on_record_merged    a record was merged, has its final ID, and is indexed.

Every hook receives a `context`. Read `context.is_new` rather than guessing
from the ID whether a record has been deployed before -- core knows, and
inferring it from the ID is how a previous version of this integration ended
up depending on the order workflow steps happened to run in.

There is nothing to register. The Provider value IS the dispatch key, so
creating the directory is what wires the integration up. A provider with no
integration directory works perfectly well -- records are created, validated,
and indexed as normal; there are simply no side effects.

Neither hook is called for Gap records, which name no provider.
"""

##############################################################################
################################## IMPORTS ###################################
##############################################################################
import os
import re
import sys

# Core's library lives in tools/. Import it if you need to parse or create
# records yourself; reusing it means your integration can never disagree with
# the indexer about what a record says.
sys.path.insert(0, os.path.join(os.getcwd(), "tools"))
import records_lib  # noqa: E402,F401  (used by the commented example below)


##############################################################################
############################## HELPER FUNCTIONS ##############################
##############################################################################
def _set_metadata_field(document, key, value):
    """Replace one value in a record's metadata table, preserving alignment.

    Prefer this over a blanket re.sub() on the document. Substituting across
    the whole file will happily rewrite matching text in the prose as well --
    replacing a schedule of "1h" everywhere also rewrites "1h" wherever an
    author mentioned it in the Overview.
    """
    pattern = rf'^(\|\s*{re.escape(key)}\s*\|)([^|\n]*)(\|)'

    def replace(match):
        width = len(match.group(2))
        return match.group(1) + f" {value}".ljust(width) + match.group(3)

    return re.sub(pattern, replace, document, count=1, flags=re.MULTILINE)


##############################################################################
#################################### HOOKS ###################################
##############################################################################
def validate_record(record, path, content, config, context):
    """Check something the configuration cannot express.

    MOST PROVIDERS DO NOT NEED THIS HOOK. Declare your fields in
    local/config.json -- under providers.<name>.fields for your provider's
    own, or core_fields for ones every record carries -- and core enforces
    them:

        "Severity": {"type": "single", "required": true,
                     "values": ["Low", "Medium", "High"]}
        "Lookback": {"type": "single", "required": true,
                     "values": ["Standard"], "pattern": "^[0-9]{1,3}[mhd]$"}

    That covers presence, enumerated values, regular expressions, and any
    combination of the two. Reach for this hook only for a rule config cannot
    state -- a relationship between two fields, say, or a value whose legality
    depends on the record's type.

    Runs in the standard validation pass, on every pull request and on an
    offline full-corpus run, so it MUST be pure: no writes, no network calls.

    Returns a list of error strings. An empty list means valid.
    """
    errors = []
    details = record.get('provider_details', {})

    # Example of a genuine cross-field rule: a retro detection must look back
    # further than it runs. No per-field declaration can say that.
    if details.get('detection_type') == "Retro":
        if details.get('lookback') == details.get('schedule'):
            errors.append(
                "a Retro detection's Lookback must be longer than its "
                "Schedule."
            )

    return errors


def on_record_created(path, record_type, config, context):
    """Called after a record has been scaffolded from its template.

    Use this to do whatever your provider needs when new coverage is started:
    create a rule or ticket on the provider's platform, reserve an identifier,
    write provider IDs back into the record.

    Arguments:
        path         path to the new record's README.md
        record_type  "Coverage" (gap records never reach here)
        config       the parsed local/config.json
        context      what core knows about this call:
                       context.provider    the Provider value that
                                           dispatched to this module
                       context.options     dict of the create workflow's
                                           inputs. Core forwards every input
                                           verbatim, so you can add dropdowns
                                           to your copy of create-record.yml
                                           and read them here without core
                                           needing to know they exist.
                       context.branch      the branch the record is about to
                                           be pushed to: the final, checked
                                           name, always set by the workflow.
                                           None when the script is run by
                                           hand without --branch.
                       context.branch_url  that branch's GitHub URL, or None
                                           outside GitHub Actions.

    Returns:
        A list of paths for any COMPANION records you created, or None. Core
        reports them alongside the primary record so the workflow commits them
        all. Returning None is normal.

    Raise or sys.exit() on failure. Core does not swallow errors here, and a
    half-created record is worse than a failed create.
    """
    # Inputs from your copy of the create workflow arrive in
    # `context.options`. Validate them rather than trusting the form.
    widget = context.options.get('example_widget')
    if widget and widget not in ("alpha", "beta"):
        sys.exit(f"Unrecognized widget: {widget}")

    # Typically: call your platform's API, then write the IDs it issued back
    # into the record so the metadata points at the real object.
    #
    #     new_id = my_platform.create_rule(...)
    #
    # Replace the placeholder your template ships with the real value. Note
    # the helper rather than a document-wide substitution.
    with open(path, "r") as f:
        document = f.read()

    document = _set_metadata_field(document, "Provider Rule ID", "EXAMPLE-123")

    with open(path, "w") as f:
        f.write(document)

    # To find a new platform object's record again before it merges, record
    # the branch on the platform side -- in a label, tag, or description. Use
    # context.branch rather than the branch_name input: the input is whatever
    # was typed, or blank, while context.branch is the name actually pushed.
    #
    #     if context.branch:
    #         my_platform.add_tag(new_id, f"branch:{context.branch}")
    #         my_platform.set_notes(new_id, f"In review: {context.branch_url}")
    #
    # The branch is deleted after merge, so on_record_merged is the place to
    # replace it with the record's permanent ID.

    # If this provider needs more than one record for a single piece of
    # coverage, create the companions here. Placeholder IDs 0-9 are available;
    # the primary record already used 0.
    #
    #     companion = records_lib.create_new_record(
    #         record_type, provider, config, placeholder_id=1
    #     )
    #     return [companion]

    return None


def on_record_changed(record, path, content, config, context):
    """Called on every pull request that touches a record, after validation.

    This is where the repository and your platform are reconciled while the
    change is still under review. Two shapes are common:

      Pure detection-as-code -- the repository is authoritative for the rule
      logic too. Read it from the record and push it to the platform.

      Compromise -- the platform owns the authoring surface for the logic
      (a rule builder UI, say) and nothing else. Pull the current logic from
      the platform and write it into the record folder, so the PR contains it
      and a reviewer can see it.

    Core supports both: anything written to the working tree here is committed
    back to the PR branch afterwards. The direction is your choice.

    Deploying from here is also allowed. Some teams want a new detection
    running in a test mode as soon as the PR opens, so alert volume and
    filtering can be assessed before it reaches production. Others want
    nothing to happen until merge. Core takes no position -- use
    `context.is_new` to tell the two situations apart.

    Returns nothing. Raise or sys.exit() on failure.
    """
    if context.is_new:
        print(f"{record['id']} has never been deployed.")
        # e.g. deploy to a test mode so alerts can be assessed during review
    else:
        print(f"{record['id']} is already deployed; updating in place.")

    # Writing to the record folder is fine; core commits it to the PR branch.
    #
    #     logic = my_platform.export_rule(rule_id)
    #     pathlib.Path(path).parent.joinpath("logic.json").write_text(logic)


def on_record_merged(record, path, content, config, context):
    """Called after a record has been merged, assigned an ID, and indexed.

    Use this to push the finished record back to your provider: update a
    description, attach the documentation URL, flip a rule out of test mode.

    Arguments:
        record   the indexed record as a dict. Core fields are top level;
                 everything provider-specific is nested under
                 'provider_details', with keys lowercased and spaces replaced
                 by underscores, so "AVL Rule" becomes 'avl_rule'.
        path     path to the record's README.md, after ID assignment
        content  the record's full markdown text
        config   the parsed local/config.json

    Returns nothing. Raise or sys.exit() on failure.

    This runs on every merge that touches the record, not just the first, so
    it should be safe to run repeatedly. `context.is_new` is True only when
    core assigned the record its ID in this same run.
    """
    details = record.get('provider_details', {})
    rule_id = details.get('provider_rule_id')

    if not rule_id:
        print("No provider rule on this record; nothing to update.")
        return

    # Retired coverage usually wants different handling from active coverage.
    if record.get('status') != "Active":
        print(f"{record['id']} is retired; skipping provider update.")
        return

    # A documentation link back to the record is often the most useful thing
    # to send. REPO_URL is supplied by the merge workflow.
    repo_url = os.getenv('REPO_URL', '')
    print(f"Would update {rule_id} with {repo_url}{path}")
