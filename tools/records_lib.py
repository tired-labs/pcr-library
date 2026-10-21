##############################################################################
################################## IMPORTS ###################################
##############################################################################
import json
import os
import re

##############################################################################
############################## GLOBAL VARIABLES ##############################
##############################################################################
CONFIG_FILE = os.path.join("local", "config.json")
RECORDS_DIR = "records"
CORE_TEMPLATE_DIR = "templates"
LOCAL_TEMPLATE_DIR = os.path.join("local", "templates")
INTEGRATIONS_DIR = os.path.join("local", "integrations")

# Universal placeholder prefix. A record uses this until an ID is assigned at
# merge, in every deployment regardless of the configured prefix, so that the
# templates and documentation need no per-instance templating. The range 0-9
# exists because one create action can scaffold several related records at once.
PLACEHOLDER_PREFIX = "cr"
PLACEHOLDER_MAX = 9

PREFIX_PATTERN = r"^[A-Z][A-Z0-9]{1,7}$"

# Fields every record carries regardless of configuration. Everything else
# comes from config: 'core_fields' names the rest, and anything not named
# there is provider-specific and nests under 'provider_details'.
#
# 'id', 'type' and 'provider' are here rather than in config because core
# reasons about them directly -- an ID is matched against the prefix, a type
# decides whether a provider is required at all.
STRUCTURAL_KEYS = {'id', 'type', 'provider'}

FIELD_TYPE_SINGLE = "single"
FIELD_TYPE_LIST = "list"
FIELD_TYPES = (FIELD_TYPE_SINGLE, FIELD_TYPE_LIST)

# The record types. These are semantics rather than configuration: core
# reasons about them directly, so a repository cannot invent its own.
#
#   Coverage     something detects or prevents the procedure; names the
#                provider that supplies it
#   Gap          the procedure was assessed and cannot be covered
#   Opportunity  a way the procedure could be detected, described without
#                implementation detail. It is not coverage, so it names no
#                provider. Published opportunities are what an organization
#                turns into its own coverage and gap records.
TYPE_COVERAGE = "Coverage"
TYPE_GAP = "Gap"
TYPE_OPPORTUNITY = "Opportunity"
RECORD_TYPES = (TYPE_COVERAGE, TYPE_GAP, TYPE_OPPORTUNITY)

# Record types that must not name a provider.
PROVIDERLESS_TYPES = (TYPE_GAP, TYPE_OPPORTUNITY)


class HookContext:
    """What core knows about the situation a hook is being called in.

    Passed to every hook so that providers never have to infer state from
    the record itself. `is_new` in particular used to be guessed from whether
    the ID still looked like a placeholder, which only worked because of the
    order steps happened to run in.

    Deliberately narrow: config, the record, and the index are already
    separate arguments to the hooks and tasks that receive them, so carrying
    copies here would only create two ways to reach the same object.
    """

    def __init__(self, event, is_new=False, options=None, provider=None):
        self.event = event              # created | changed | merged | validate
        self.is_new = is_new            # never deployed before
        self.options = options or {}    # create workflow / task inputs
        self.provider = provider        # the value that dispatched here

    def __repr__(self):
        return (
            f"HookContext(event={self.event!r}, is_new={self.is_new}, "
            f"provider={self.provider!r})"
        )


class ConfigError(Exception):
    """Raised when the repository configuration is missing or invalid."""


class ParseError(Exception):
    """Raised when a record cannot be parsed into an index entry."""


##############################################################################
############################# LIBRARY FUNCTIONS ##############################
##############################################################################
def field_key(display_name):
    """Transform a metadata display name into its internal key.

    Config and the record's metadata table both use the human-readable name
    ("AVL Rule"); index.json and hook code see the transformed key
    ("avl_rule"). Core owns the transform so that a config author only ever
    types what they can see in the record.
    """
    return display_name.lower().replace(" ", "_")


def _validate_field_spec(where, name, spec):
    """Check one field declaration, raising ConfigError on anything wrong.

    Done at load time so a malformed regex or a missing type fails with a
    clear message instead of at first use against a real record.
    """
    if not isinstance(spec, dict):
        raise ConfigError(f"{where} field '{name}' must be an object.")

    field_type = spec.get('type')
    if field_type is None:
        raise ConfigError(
            f"{where} field '{name}' is missing 'type'. It must be "
            f"'{FIELD_TYPE_SINGLE}' (one value) or '{FIELD_TYPE_LIST}' "
            f"(a comma-separated list)."
        )
    if field_type not in FIELD_TYPES:
        raise ConfigError(
            f"{where} field '{name}' has type '{field_type}'. It must be "
            f"one of: {', '.join(FIELD_TYPES)}."
        )

    if 'required' in spec and not isinstance(spec['required'], bool):
        raise ConfigError(
            f"{where} field '{name}': 'required' must be true or false."
        )

    if 'values' in spec:
        if not isinstance(spec['values'], list) or not spec['values']:
            raise ConfigError(
                f"{where} field '{name}': 'values' must be a non-empty list."
            )

    if 'pattern' in spec:
        try:
            re.compile(spec['pattern'])
        except re.error as e:
            raise ConfigError(
                f"{where} field '{name}': 'pattern' is not a valid regular "
                f"expression: {e}"
            )


def _validate_fields_block(where, fields):
    if not isinstance(fields, dict):
        raise ConfigError(f"{where} 'fields' must be an object.")
    for name, spec in fields.items():
        _validate_field_spec(where, name, spec)


def check_field(display_name, spec, value, present):
    """Check one field's value against its declaration.

    Returns a list of error strings.

      present  the metadata table has a row for this field
      value    [] / "" when the row is empty, None when it is absent

    Comparison is case-insensitive: whether an author writes "High" or "high"
    is their business, and the record stores what they wrote.
    """
    errors = []

    if not present:
        # A declared field with no row at all is a shape problem: the record
        # has drifted from the template, and the value is silently lost.
        errors.append(
            f"metadata table has no '{display_name}' row."
        )
        return errors

    is_empty = value is None or value == "" or value == []

    if spec.get('required', False) and is_empty:
        errors.append(f"'{display_name}' is required but empty.")
        return errors

    if is_empty:
        return errors

    values = spec.get('values')
    pattern = spec.get('pattern')
    if not values and not pattern:
        return errors

    # A list field is checked per item; a single field as a whole.
    items = value if isinstance(value, list) else [value]

    for item in items:
        text = str(item)
        ok = False
        if values and text.lower() in [str(v).lower() for v in values]:
            ok = True
        if not ok and pattern and re.match(pattern, text, re.IGNORECASE):
            ok = True
        if ok:
            continue

        expected = []
        if values:
            expected.append("one of: " + ", ".join(str(v) for v in values))
        if pattern:
            expected.append(f"matching /{pattern}/")
        errors.append(
            f"'{display_name}' value '{text}' is not permitted "
            f"({' or '.join(expected)})."
        )

    return errors


def load_config(path=CONFIG_FILE):
    """Read and sanity check this repository's configuration."""
    if not os.path.exists(path):
        raise ConfigError(
            f"{path} not found. Copy local/config.example.json to {path} and "
            "set it up for this repository. See docs/DEPLOYMENT.md."
        )

    with open(path, "r") as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(f"{path} is not valid JSON: {e}")

    prefix = config.get('id_prefix')
    if not prefix:
        raise ConfigError(f"{path} is missing 'id_prefix'.")

    if prefix == "XXXX":
        raise ConfigError(
            "'id_prefix' is still set to the example placeholder 'XXXX'. Set "
            f"it to this repository's own prefix (for example 'PCR') in {path} "
            "before creating any records."
        )

    if not re.match(PREFIX_PATTERN, prefix):
        raise ConfigError(
            f"'id_prefix' value '{prefix}' is invalid. It must be 2-8 "
            "characters, uppercase letters and digits only, starting with a "
            "letter."
        )

    if not config.get('providers'):
        raise ConfigError(
            f"{path} defines no providers. At least one is required for "
            "coverage records."
        )

    config.setdefault('core_fields', {})

    if not config.get('platforms'):
        raise ConfigError(f"{path} is missing 'platforms'.")

    _validate_fields_block("Core", config['core_fields'])

    for name, provider in config['providers'].items():
        if not isinstance(provider, dict):
            raise ConfigError(f"Provider '{name}' must be an object.")
        provider.setdefault('fields', {})
        _validate_fields_block(f"Provider '{name}'", provider['fields'])

        # A provider cannot redeclare a core field: core's declaration wins
        # and two sources for one field is how they drift apart.
        clash = set(provider['fields']) & set(config['core_fields'])
        if clash:
            raise ConfigError(
                f"Provider '{name}' redeclares core field(s): "
                f"{', '.join(sorted(clash))}. Remove them from the provider."
            )

    return config


def resolve_template(record_type, provider, config):
    """Return the template path for a record type and provider.

    Gap and opportunity records have no provider and use their own templates.
    Coverage records
    use their provider's template. An instance's own templates live in
    local/templates and take precedence over the core ones, so an instance can
    override a base template without editing it.
    """
    if record_type == TYPE_GAP:
        filename = config.get('gap_template', 'gap-template.md')
    elif record_type == TYPE_OPPORTUNITY:
        filename = config.get('opportunity_template', 'opportunity-template.md')
    else:
        provider_config = config['providers'].get(provider)
        if provider_config is None:
            raise ConfigError(
                f"Provider '{provider}' is not configured. Add it to "
                f"'providers' in {CONFIG_FILE}."
            )
        filename = provider_config.get('template', 'coverage-template.md')

    for directory in (LOCAL_TEMPLATE_DIR, CORE_TEMPLATE_DIR):
        candidate = os.path.join(directory, filename)
        if os.path.exists(candidate):
            return candidate

    raise ConfigError(
        f"Template '{filename}' was not found in {LOCAL_TEMPLATE_DIR} or "
        f"{CORE_TEMPLATE_DIR}."
    )


def common_keys(config):
    """Keys that stay at the top level of an index entry.

    Derived from the 'core_fields' block rather than declared separately, so
    adding a core field cannot silently leave it nesting into
    provider_details.
    """
    keys = set(STRUCTURAL_KEYS)
    keys.update(field_key(name) for name in config.get('core_fields', {}))
    return keys


def convert_flat_meta_to_index_dict(record_meta, config):
    """Nest provider-specific keys under 'provider_details' for the index."""
    keep = common_keys(config)
    record_meta['provider_details'] = {
        key: record_meta.pop(key)
        for key in list(record_meta.keys())
        if key not in keep
    }
    return record_meta


def validate_metadata(record_meta, config):
    """Check a record's metadata against this repository's configuration.

    Returns a list of error strings; an empty list means the record is valid.

    Field values are checked from the declarations in config -- core fields
    for every record, plus the named provider's fields for coverage records.
    A provider only needs a validate_record hook for something config cannot
    express.
    """
    errors = []
    prefix = config['id_prefix']

    record_id = record_meta.get('id', '')
    placeholder = rf"^{PLACEHOLDER_PREFIX}\d{{4}}$"
    if not (re.match(rf"^{prefix}\d{{4}}$", record_id, re.IGNORECASE)
            or re.match(placeholder, record_id, re.IGNORECASE)):
        errors.append(
            f"ID '{record_id}' does not match this repository's prefix. "
            f"Expected '{prefix}' followed by four digits, or a "
            f"'{PLACEHOLDER_PREFIX.upper()}000N' placeholder for a new record."
        )

    record_type = record_meta.get('type')
    if record_type not in RECORD_TYPES:
        errors.append(
            f"Type '{record_type}' is not a valid record type "
            f"({', '.join(RECORD_TYPES)})."
        )

    # Provider is required for coverage, and absent for gap and opportunity
    # records.
    provider = record_meta.get('provider')
    if record_type == TYPE_COVERAGE:
        if not provider:
            errors.append("Coverage records must name a Provider.")
        elif provider not in config['providers']:
            errors.append(
                f"Provider '{provider}' is not configured. Add it to "
                f"'providers' in {CONFIG_FILE}."
            )
    elif record_type == TYPE_GAP and provider:
        errors.append(
            "Gap records describe missing coverage and must not name a "
            "Provider."
        )
    elif record_type == TYPE_OPPORTUNITY and provider:
        errors.append(
            "Opportunity records describe a possible detection, not an "
            "implemented one, and must not name a Provider."
        )

    # Every declared field, core and provider alike, checked the same way.
    known_provider = provider in config.get('providers', {})
    specs = all_field_specs(config, provider if known_provider else None)

    for display_name, spec in specs.items():
        key = field_key(display_name)
        errors.extend(
            check_field(
                display_name, spec,
                record_meta.get(key),
                present=key in record_meta,
            )
        )

    # Platforms doubles as the folder-code lookup, so it is checked against
    # that map rather than against a values list.
    platforms = config.get('platforms')
    if platforms and record_meta.get('platforms'):
        known = {name.lower() for name in platforms}
        for platform in record_meta['platforms']:
            if platform.lower() not in known:
                errors.append(f"Platform '{platform}' is not configured.")

    return errors


def parse_meta_table(meta_table):
    temp_dict = {}
    for line in meta_table[2:]:
        if len(line) != 0:
            elements = line.split("|")
            temp_dict[elements[1].strip()] = elements[2].strip()
    return temp_dict


def all_field_specs(config, provider=None):
    """Every field declaration that applies to a record, keyed by display name.

    Core fields apply to all records; a provider's fields layer on top for
    the coverage records that name it.
    """
    specs = dict(config.get('core_fields', {}))
    if provider:
        specs.update(
            config.get('providers', {}).get(provider, {}).get('fields', {})
        )
    return specs


def parse_record_metadata(record_content, config):
    """Parse a record's markdown into a flat metadata dict.

    Values are typed from the configuration rather than guessed: a field
    declared 'list' is split on commas, a 'single' field is kept whole.

    Absence and emptiness are kept distinct, which is what lets validation
    tell "the author left Tactics blank" from "the Tactics row was deleted":

        absent row      the key is not in the dict at all
        empty row       [] for a list field, "" for a single field
    """
    record_dict = {}
    meta_section_found = False
    meta_table = []

    if isinstance(record_content, str):
        record_content = record_content.splitlines()

    for line in record_content:
        if line.strip().startswith("# "):
            record_dict['Title'] = line.strip()[2:]

        if line.strip() == "## Metadata":
            meta_section_found = True
            continue

        if meta_section_found and line.startswith("|"):
            # Some values are links and enclosed in brackets; strip them.
            line = line.replace("]", "").replace("[", "")
            meta_table.append(line.strip())

    if not meta_table:
        raise ParseError("no '## Metadata' table found.")

    record_dict.update(parse_meta_table(meta_table))

    # A provider's fields only apply once we know which provider it names.
    specs = all_field_specs(config, record_dict.get('Provider'))

    for display_name, spec in specs.items():
        if display_name not in record_dict:
            continue                      # absent: leave the key out entirely
        raw = record_dict[display_name]
        if spec.get('type') == FIELD_TYPE_LIST:
            record_dict[display_name] = (
                [item.strip() for item in raw.split(",") if item.strip()]
                if raw.strip() else []
            )

    # Config and the metadata table use display names; the index and hooks
    # see the transformed key.
    record_dict = {
        field_key(key): value for key, value in record_dict.items()
    }

    if 'id' not in record_dict:
        raise ParseError("the metadata table has no 'ID' field.")

    return record_dict


def integration_hook(provider, hook_name):
    """Return a provider's hook function, or None if it has none.

    The Provider metadata value is the dispatch key: coverage supplied by
    'Anvilogic' looks for local/integrations/anvilogic/hooks.py. A repository
    with no integrations has no hooks and every call is a no-op.
    """
    if not provider:
        return None

    slug = re.sub(r'[^a-z0-9]+', '-', provider.lower()).strip('-')
    hook_path = os.path.join(INTEGRATIONS_DIR, slug, "hooks.py")
    if not os.path.exists(hook_path):
        return None

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        f"integrations_{slug}", hook_path
    )
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise ConfigError(f"Could not load {hook_path}: {e}")

    return getattr(module, hook_name, None)


def iter_provider_records(files, provider, config):
    """Yield (path, metadata) for records supplied by one provider.

    Saves every integration reimplementing the same loop-open-parse-filter
    preamble.
    """
    for path in files:
        try:
            with open(path, "r") as f:
                content = f.read()
        except OSError:
            continue

        try:
            meta = parse_record_metadata(content, config)
        except ParseError:
            continue

        if meta.get('type') == TYPE_COVERAGE and meta.get('provider') == provider:
            yield path, meta


def provider_task(provider, task_name):
    """Return a named task from a provider's tasks.py, or None.

    Tasks are operations run outside a record's lifecycle -- reconciliation,
    audits, bulk syncs. They are invoked by tools/run-provider-task.py rather
    than by an event.
    """
    if not provider:
        return None

    slug = re.sub(r'[^a-z0-9]+', '-', provider.lower()).strip('-')
    task_path = os.path.join(INTEGRATIONS_DIR, slug, "tasks.py")
    if not os.path.exists(task_path):
        return None

    import importlib.util
    spec = importlib.util.spec_from_file_location(f"tasks_{slug}", task_path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise ConfigError(f"Could not load {task_path}: {e}")

    return getattr(module, task_name, None)


def create_new_record(record_type, provider, config, placeholder_id=0):
    """Scaffold a new record folder from the appropriate template.

    Returns the path to the new README.md. placeholder_id lets one create
    action scaffold several related records at once; each gets its own
    placeholder folder until IDs are assigned at merge.
    """
    if placeholder_id < 0 or placeholder_id > PLACEHOLDER_MAX:
        raise ConfigError(
            f"Placeholder ID must be 0-{PLACEHOLDER_MAX}, got {placeholder_id}."
        )

    template_path = resolve_template(record_type, provider, config)
    with open(template_path, "r") as f:
        template = f.read()

    new_id = f"{PLACEHOLDER_PREFIX.upper()}000{placeholder_id}"
    template = re.sub(
        rf"{PLACEHOLDER_PREFIX.upper()}0000", new_id, template
    )

    folder_path = os.path.join(RECORDS_DIR, new_id.lower())
    if os.path.exists(folder_path):
        raise ConfigError(
            f"{folder_path} already exists. Finish or remove the record "
            "already in progress before creating another."
        )
    os.makedirs(folder_path)

    file_path = os.path.join(folder_path, "README.md")
    with open(file_path, "w") as f:
        f.write(template)

    return file_path
