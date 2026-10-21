##############################################################################
################################## IMPORTS ###################################
##############################################################################
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import records_lib
from records_lib import ConfigError

##############################################################################
#################################### MAIN ####################################
##############################################################################
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Scaffold a new coverage record from the appropriate template. "
            "A provider integration may scaffold several related records in "
            "one action; each gets its own placeholder folder until IDs are "
            "assigned at merge. Run from the repository root."
        )
    )
    parser.add_argument(
        '-t', '--type', required=True,
        help="Record type, e.g. 'Coverage' or 'Gap'."
    )
    parser.add_argument(
        '-p', '--provider',
        help="Provider supplying the coverage. Omit for Gap records."
    )
    parser.add_argument(
        '-o', '--options', default="{}",
        help=(
            "JSON object of extra options, passed through to the provider's "
            "on_record_created hook. The create workflow forwards its own "
            "inputs here, so an integration can collect whatever it needs "
            "without the core script knowing about those fields."
        )
    )

    args = parser.parse_args()

    try:
        config = records_lib.load_config()
    except ConfigError as e:
        sys.exit(f"Configuration error: {e}")

    if args.type not in records_lib.RECORD_TYPES:
        sys.exit(
            f"Record type '{args.type}' is not valid. Valid types: "
            f"{', '.join(records_lib.RECORD_TYPES)}"
        )

    if args.type == records_lib.TYPE_COVERAGE and not args.provider:
        sys.exit("Coverage records require a provider (-p/--provider).")

    if args.type in records_lib.PROVIDERLESS_TYPES and args.provider:
        sys.exit(f"{args.type} records name no provider; omit --provider.")

    try:
        options = json.loads(args.options)
    except json.JSONDecodeError as e:
        sys.exit(f"--options is not valid JSON: {e}")

    # Create the primary record first. A provider integration may then ask for
    # additional related records, which is why placeholder IDs run 0-9.
    try:
        created = [
            records_lib.create_new_record(
                args.type, args.provider, config, placeholder_id=0
            )
        ]
    except ConfigError as e:
        sys.exit(f"Error creating record: {e}")

    print(f"Created {created[0]}")

    try:
        hook = records_lib.integration_hook(
            args.provider, "on_record_created"
        )
    except ConfigError as e:
        sys.exit(f"Integration error: {e}")

    if hook:
        print(f"Running {args.provider} on_record_created hook.")
        try:
            extra = hook(
                path=created[0], record_type=args.type,
                provider=args.provider, options=options, config=config,
            )
        except Exception as e:
            sys.exit(f"{args.provider} on_record_created hook failed: {e}")

        # A hook may return paths of additional records it scaffolded.
        if extra:
            created.extend(extra)
            for path in extra:
                print(f"Created {path}")

    # Report every created path so the calling workflow can act on them.
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f:
        f.write(f"created={' '.join(created)}\n")

    sys.exit(0)
