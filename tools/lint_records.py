##############################################################################
################################## IMPORTS ###################################
##############################################################################
import re
import subprocess
import sys

##############################################################################
############################## GLOBAL VARIABLES ##############################
##############################################################################
RULES = ".tiredize/rules.yaml"

# Each record type's section structure. Coverage and gap records share one;
# opportunity records describe what could be detected, so they have their own.
SCHEMA_BY_TYPE = {
    "opportunity": ".tiredize/schema-opportunity.yaml",
}
DEFAULT_SCHEMA = ".tiredize/schema.yaml"

TYPE_ROW = re.compile(r"^\|\s*Type\s*\|\s*([^|]*?)\s*\|", re.MULTILINE)


##############################################################################
############################## HELPER FUNCTIONS ##############################
##############################################################################
def schema_for(path):
    """The schema for a record, chosen by the Type row of its metadata table.

    A file with no recognizable Type gets the default schema; validation
    reports the missing or unknown type separately.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            match = TYPE_ROW.search(f.read())
    except OSError:
        return DEFAULT_SCHEMA
    if not match:
        return DEFAULT_SCHEMA
    return SCHEMA_BY_TYPE.get(match.group(1).strip().lower(), DEFAULT_SCHEMA)


##############################################################################
#################################### MAIN ####################################
##############################################################################
if __name__ == "__main__":
    """Lint record markdown, each file against the schema for its type.

    Tiredize applies one schema per run, and record types differ in their
    sections, so the files are grouped by schema and linted in one run per
    group. Exits non-zero if any group has findings.

        python3 tools/lint_records.py records/pcr0010/README.md ...
    """
    files = sys.argv[1:]
    if not files:
        print("No files given; nothing to lint.")
        sys.exit(0)

    groups = {}
    for path in files:
        groups.setdefault(schema_for(path), []).append(path)

    failed = False
    for schema, paths in sorted(groups.items()):
        print(f"Linting {len(paths)} file(s) against {schema}")
        result = subprocess.run(
            ["tiredize", "--markdown-schema", schema, "--rules", RULES, *paths]
        )
        if result.returncode != 0:
            failed = True

    sys.exit(1 if failed else 0)
