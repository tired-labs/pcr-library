##############################################################################
################################## IMPORTS ###################################
##############################################################################
import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import records_lib
from records_lib import ConfigError, ParseError

INDEX_FILE = "index.json"

# Version of the index.json envelope this tool writes. Consumers read it to
# decide whether they understand the file, so bump it only when the shape
# changes in a way that would break them.
INDEX_SCHEMA = 2


##############################################################################
############################## HELPER FUNCTIONS ##############################
##############################################################################
def update_index(record_dict, index):
    today_string = datetime.date.today().strftime("%Y-%m-%d")

    for record in index:
        if record['id'] == record_dict['id']:
            print("Found ID in index already, updating it")
            for key in record:
                if key in record_dict:  # pub_date only exists in the index
                    record[key] = record_dict[key]
            return

    record_dict['pub_date'] = today_string
    index.append(record_dict)


def next_available_id(index, prefix):
    """Return the next free ID.

    The highest assigned number is found by scanning every entry, not by
    reading the last one -- merge order does not guarantee the index is
    sorted, so trusting the tail can hand out an ID that is already in use.
    """
    highest = 0
    id_regex = re.compile(rf"^{prefix}(\d+)$", re.IGNORECASE)

    for record in index:
        match = id_regex.match(record.get('id', ''))
        if match:
            highest = max(highest, int(match.group(1), 10))

    # 0-9 are reserved for placeholder folders, so assignment starts at 10.
    return f"{prefix}{max(highest + 1, 10):04d}"


def assign_new_id(orig_file, new_id):
    """Rename a placeholder record folder and its contents to the new ID."""
    match = re.search(
        rf'({records_lib.PLACEHOLDER_PREFIX}\d+)', orig_file
    )
    if not match:
        sys.exit(f"Error finding placeholder ID in {orig_file}.")

    old_lower = match.group(1)
    old_upper = old_lower.upper()
    new_upper = new_id.upper()
    new_lower = new_id.lower()

    old_dir = os.path.join(records_lib.RECORDS_DIR, old_lower)
    new_dir = os.path.join(records_lib.RECORDS_DIR, new_lower)

    # Without this check a rename onto an existing folder would nest the
    # record inside it rather than failing.
    if os.path.exists(new_dir):
        sys.exit(f"Error: {new_dir} already exists; {new_upper} is assigned.")

    for root, dirs, files in os.walk(old_dir):
        for filename in files:
            filepath = os.path.join(root, filename)
            if filename == 'README.md':
                with open(filepath, 'r') as f:
                    content = f.read()
                # Anchored so that an ID merely containing the placeholder
                # as a substring is not mangled: replacing CR0000 inside
                # PCR0000 would produce PPCR0013.
                content = re.sub(rf"\b{old_upper}\b", new_upper, content)
                content = re.sub(rf"\b{old_lower}\b", new_lower, content)
                with open(filepath, 'w') as f:
                    f.write(content)
                print(f"Replaced ID in {filepath}")

            if old_lower in filename:
                new_filename = filename.replace(old_lower, new_lower)
                try:
                    os.rename(filepath, os.path.join(root, new_filename))
                    print(f"Renamed file: {filename} -> {new_filename}")
                except OSError as e:
                    sys.exit(f"Error renaming {filepath}: {e}")

    try:
        os.rename(old_dir, new_dir)
    except OSError as e:
        sys.exit(f"Error renaming {old_dir} to {new_dir}: {e}")

    print("Reassignment complete.")
    return orig_file.replace(old_lower, new_lower)


def find_all_records():
    """Return every record README.md under the records directory."""
    found = []
    for dirpath, dirnames, filenames in os.walk(records_lib.RECORDS_DIR):
        for filename in filenames:
            if filename == "README.md":
                found.append(os.path.join(dirpath, filename))
    return sorted(found)


def parse_file(path, config):
    """Read and parse one record, returning (raw_content, metadata dict)."""
    with open(path, "r") as f:
        content = f.read()
    return content, records_lib.parse_record_metadata(content, config)


##############################################################################
################################ VALIDATION ##################################
##############################################################################
def read_index(content):
    """Return the records from an index.json, envelope or not.

    Accepts the bare array written by earlier versions so that a repository
    can be reindexed after an upgrade without a migration step.
    """
    if not content.strip():
        return []

    data = json.loads(content)
    if isinstance(data, list):
        return data
    return data.get('records', [])


def build_index_document(records, config):
    """Wrap the records in the envelope consumers read.

    The platform map is copied verbatim from the repository configuration so
    that a consumer can resolve a record's platform short code without
    fetching anything else. Because validation rejects a record naming an
    unconfigured platform, every platform appearing in a record is guaranteed
    to be in this map.
    """
    return {
        "schema": INDEX_SCHEMA,
        "generated": datetime.datetime.now(
            datetime.timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platforms": config.get('platforms', {}),
        "records": records,
    }


def build_index_entry(meta, config):
    """Return the entry this record would contribute to the index.

    Coverage records nest provider-specific keys so that every coverage record
    has the same shape regardless of provider.
    """
    entry = dict(meta)
    if entry.get('type') == records_lib.TYPE_COVERAGE:
        entry = records_lib.convert_flat_meta_to_index_dict(entry, config)
    return entry


def validate_record(path, config, index):
    """Check a record's content against this repository's configuration.

    Structural validity (sections, formatting) is the linter's job. This
    checks what a generic linter cannot know: whether the values used are
    legal for THIS repository and its configured providers.
    """
    errors = []
    path_normalized = path.replace(os.sep, "/").lstrip("./")

    try:
        content, meta = parse_file(path, config)
    except ParseError as e:
        return [str(e)]
    except OSError as e:
        return [f"could not read file: {e}"]

    errors.extend(records_lib.validate_metadata(meta, config))

    # A provider knows things core cannot: which schedules its platform
    # accepts, what a valid lookback looks like. This runs in the standard
    # validation pass so those checks happen on every PR and in a full-corpus
    # run, not only alongside a deploy.
    provider = meta.get('provider')
    try:
        hook = records_lib.integration_hook(provider, "validate_record")
    except ConfigError as e:
        return errors + [str(e)]

    if hook:
        context = records_lib.HookContext(
            event="validate", provider=provider
        )
        try:
            provider_errors = hook(
                record=build_index_entry(dict(meta), config), path=path,
                content=content, config=config, context=context,
            ) or []
        except Exception as e:
            provider_errors = [f"{provider} validate_record hook failed: {e}"]
        errors.extend(provider_errors)

    match = re.match(
        rf'^{records_lib.RECORDS_DIR}/([^/]+)/README\.md$', path_normalized
    )
    if not match:
        errors.append(
            f"path is not of the form {records_lib.RECORDS_DIR}/<id>/README.md"
        )
        return errors

    folder_id = match.group(1)
    record_id = meta.get('id', '')
    if record_id.lower() != folder_id.lower():
        errors.append(
            f"ID '{record_id}' does not match its folder name '{folder_id}'."
        )

    # Referenced local files must exist.
    base = os.path.dirname(path)
    for m in re.finditer(r'!?\[[^\]]*\]\(([^)\s]+)\)', content):
        target = m.group(1).split("#")[0]
        if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target):
            continue
        if not os.path.exists(os.path.normpath(os.path.join(base, target))):
            errors.append(f"referenced file '{target}' does not exist.")

    # Another record must not already claim this ID.
    is_placeholder = record_id.lower().startswith(
        records_lib.PLACEHOLDER_PREFIX
    )
    if not is_placeholder:
        for entry in index:
            if (entry.get('id') == record_id
                    and entry.get('title') != meta.get('title')):
                errors.append(f"another record is already indexed as {record_id}.")

    return errors


##############################################################################
#################################### MAIN ####################################
##############################################################################
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Index and validate the coverage records in this repository.\n"
            "\n"
            "  index     reindex every record; writes index.json\n"
            "  merge     assign IDs to new records and update the index;\n"
            "            writes records and index.json, runs provider hooks\n"
            "  validate  check records against this repository's config and\n"
            "            show the index entry each would produce. Writes\n"
            "            nothing and calls no provider, so it is safe to run\n"
            "            locally and across the whole corpus. Use this to\n"
            "            confirm a record will merge cleanly.\n"
            "  review    validate, then run the provider's on_record_changed\n"
            "            hook. Intended for pull requests. MAY have side\n"
            "            effects: a provider can deploy or rewrite files.\n"
            "\n"
            "Run from the repository root."
        )
    )
    parser.add_argument(
        'mode', choices=['index', 'merge', 'validate', 'review']
    )
    parser.add_argument(
        '-f', '--files', nargs='+',
        help=(
            "Files to parse. Required in 'merge' and 'review' modes; "
            "optional in 'validate', which defaults to the whole repository."
        )
    )

    parser.add_argument(
        '--show-entry', action='store_true',
        help=(
            "In 'validate' and 'review', print the index entry each record "
            "would produce. Useful for confirming how a record will land."
        )
    )

    args = parser.parse_args()
    print(f"Running in {args.mode} mode.\n")

    try:
        config = records_lib.load_config()
    except ConfigError as e:
        sys.exit(f"Configuration error: {e}")

    prefix = config['id_prefix']
    today_string = datetime.date.today().strftime("%Y-%m-%d")

    # A repository starts with no index.json: the template does not ship one,
    # so that it is purely instance data and a template update can never
    # conflict with it. The first reindex creates it.
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r") as f:
            content = f.read()
    else:
        content = ""
    index = read_index(content)

    if args.mode in ("merge", "review"):
        if not args.files:
            sys.exit(
                f"Please provide a list of files in '{args.mode}' mode."
            )
        files = args.files
    elif args.mode == "validate":
        files = args.files if args.files else find_all_records()
    else:
        files = find_all_records()

    ##########################################################################
    # Validate and review modes
    #
    # review is validate plus the provider's on_record_changed hook. Keeping
    # the two in one block is what guarantees the ordering: nothing is handed
    # to a provider until every record has passed validation. Expressing that
    # as workflow step order instead would let one run without the other.
    ##########################################################################
    if args.mode in ("validate", "review"):
        if not files:
            print(f"No records found to {args.mode}.")
            sys.exit(0)

        total = 0
        for path in files:
            errors = validate_record(path, config, index)
            if errors:
                total += len(errors)
                print(f"[-] {path}")
                for error in errors:
                    print(f"      {error}")
                continue

            print(f"[+] {path}")

            # Show what this record would contribute to the index. Cheap, and
            # it means a reviewer can see the indexed shape without a separate
            # dry-run mode.
            if args.show_entry:
                try:
                    _, meta = parse_file(path, config)
                    print("      would index as:")
                    print(f"      {build_index_entry(meta, config)}")
                except ParseError:
                    pass

        print()
        if total:
            print(f"[-] Finished: {total} error(s) in {len(files)} record(s)")
            sys.exit(1)

        print(f"[+] Finished: 0 errors found in {len(files)} record(s)")

        if args.mode == "validate":
            sys.exit(0)

        ######################################################################
        # review: validation passed, so hand each record to its provider
        ######################################################################
        for path in files:
            try:
                content, meta = parse_file(path, config)
            except ParseError as e:
                sys.exit(f"Parsing error in {path}: {e}")

            provider = meta.get('provider')
            try:
                hook = records_lib.integration_hook(
                    provider, "on_record_changed"
                )
            except ConfigError as e:
                sys.exit(f"Integration error: {e}")

            if not hook:
                continue

            # A record still in a placeholder folder has never been merged,
            # so the provider has never deployed it. Core knows this; the
            # provider should not have to infer it from the ID.
            is_new = os.path.basename(os.path.dirname(path)).startswith(
                records_lib.PLACEHOLDER_PREFIX
            )
            context = records_lib.HookContext(
                event="changed", is_new=is_new, provider=provider
            )

            print(f"Running {provider} on_record_changed hook for {path}.")
            try:
                hook(record=build_index_entry(dict(meta), config), path=path,
                     content=content, config=config, context=context)
            except Exception as e:
                sys.exit(f"{provider} on_record_changed hook failed: {e}")

        sys.exit(0)

    ##########################################################################
    # Index / merge modes
    ##########################################################################
    for path in files:
        print(f"Parsing file: {path}")

        is_new = False
        if args.mode == "merge":
            placeholder_dir = os.path.join(
                records_lib.RECORDS_DIR, records_lib.PLACEHOLDER_PREFIX
            )
            if path.startswith(placeholder_dir):
                # This record has never been merged, so its provider has never
                # deployed it. Core knows that here; passing it in the context
                # spares providers from inferring it from the ID, which used
                # to depend on the order workflow steps happened to run in.
                is_new = True
                new_id = next_available_id(index, prefix)
                print(
                    "New record detected, assigning a new ID number. "
                    f"Next available ID is {new_id}"
                )
                path = assign_new_id(path, new_id)

        try:
            content, record_dict = parse_file(path, config)
        except ParseError as e:
            sys.exit(f"Parsing error in {path}: {e}")

        # Coverage records nest provider-specific keys so that every coverage
        # record has the same shape in the index regardless of provider.
        provider = record_dict.get('provider')
        if record_dict.get('type') == records_lib.TYPE_COVERAGE:
            record_dict = records_lib.convert_flat_meta_to_index_dict(
                record_dict, config
            )

        if args.mode == "merge":
            record_dict['last_update'] = today_string

        update_index(record_dict, index)

        # Hand off to the provider's integration, if this repository has one.
        # The Provider value is the dispatch key; a repository with no
        # integrations simply has no hook and nothing happens here.
        if args.mode == "merge":
            try:
                hook = records_lib.integration_hook(provider, "on_record_merged")
            except ConfigError as e:
                sys.exit(f"Integration error: {e}")

            if hook:
                context = records_lib.HookContext(
                    event="merged", is_new=is_new, provider=provider
                )
                print(f"Running {provider} on_record_merged hook.")
                try:
                    hook(record=record_dict, path=path, content=content,
                         config=config, context=context)
                except Exception as e:
                    sys.exit(f"{provider} on_record_merged hook failed: {e}")

    print("Writing updated index")
    with open(INDEX_FILE, "w") as f:
        f.write(json.dumps(build_index_document(index, config), indent=2))
        f.write("\n")

    sys.exit(0)
