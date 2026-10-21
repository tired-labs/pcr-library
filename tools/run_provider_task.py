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

INDEX_FILE = "index.json"


##############################################################################
#################################### MAIN ####################################
##############################################################################
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Run a named task belonging to a provider integration.\n"
            "\n"
            "Hooks cover a record's lifecycle: created, changed, merged. "
            "Some provider work does not belong to any record's lifecycle -- "
            "reconciling the provider's state against this repository, "
            "auditing, bulk operations. Those are tasks, invoked on a "
            "schedule or by hand rather than by an event.\n"
            "\n"
            "Core resolves the provider, loads the configuration and the "
            "index, and calls the named function in "
            "local/integrations/<slug>/tasks.py. The provider owns what the "
            "task does; core owns getting it called. Adding a task needs no "
            "change to core.\n"
            "\n"
            "Run from the repository root."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'provider',
        help="Provider whose task to run, as named in the config (e.g. Anvilogic)."
    )
    parser.add_argument(
        'task',
        help="Function name to call in that provider's tasks.py."
    )
    parser.add_argument(
        '-f', '--files', nargs='+',
        help="Optional list of files to pass to the task."
    )
    parser.add_argument(
        '-o', '--options', default="{}",
        help="JSON object of extra options, passed through to the task."
    )

    args = parser.parse_args()

    try:
        config = records_lib.load_config()
    except ConfigError as e:
        sys.exit(f"Configuration error: {e}")

    if args.provider not in config['providers']:
        sys.exit(
            f"Provider '{args.provider}' is not configured. Valid providers: "
            f"{', '.join(config['providers'])}"
        )

    try:
        options = json.loads(args.options)
    except json.JSONDecodeError as e:
        sys.exit(f"--options is not valid JSON: {e}")

    try:
        task = records_lib.provider_task(args.provider, args.task)
    except ConfigError as e:
        sys.exit(f"Integration error: {e}")

    if task is None:
        sys.exit(
            f"Provider '{args.provider}' has no task named '{args.task}'. "
            f"Define it in local/integrations/<slug>/tasks.py."
        )

    # A repository starts with no index.json: the template does not ship one,
    # so that it is purely instance data and a template update can never
    # conflict with it. The first reindex creates it.
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r") as f:
            content = f.read()
    else:
        content = ""
    # index.json is a schema-2 envelope; tasks receive just its records. A
    # bare array is still accepted, from before the envelope.
    data = json.loads(content) if content.strip() else []
    index = data.get('records', []) if isinstance(data, dict) else data

    context = records_lib.HookContext(
        event=f"task:{args.task}", options=options, provider=args.provider
    )

    print(f"Running {args.provider} task '{args.task}'.\n")
    try:
        result = task(
            files=args.files, config=config, context=context, index=index
        )
    except Exception as e:
        sys.exit(f"{args.provider} task '{args.task}' failed: {e}")

    # A task signals failure by returning a non-zero int or False; anything
    # else is treated as success so that a task returning data still passes.
    if result is False:
        sys.exit(1)
    if isinstance(result, int) and not isinstance(result, bool):
        sys.exit(result)

    sys.exit(0)
