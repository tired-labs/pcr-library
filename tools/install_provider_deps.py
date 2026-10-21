##############################################################################
################################## IMPORTS ###################################
##############################################################################
import glob
import os
import subprocess
import sys

INTEGRATIONS_GLOB = os.path.join("local", "integrations", "*", "requirements.txt")


##############################################################################
#################################### MAIN ####################################
##############################################################################
if __name__ == "__main__":
    """Install whatever this repository's integrations declare they need.

    A provider integration that depends on a vendor library declares it in
    local/integrations/<slug>/requirements.txt, and every workflow that might
    call a hook runs this one command. That keeps an integration's
    dependencies inside the integration's own directory: adding a provider
    never means editing a workflow, and core never learns the name of a
    vendor package.

    Nothing to install is the normal case, not an error -- a repository with
    no integrations, or with integrations that need nothing beyond the
    standard library, exits cleanly here.
    """
    requirement_files = sorted(glob.glob(INTEGRATIONS_GLOB))

    if not requirement_files:
        print("No integration dependencies declared.")
        sys.exit(0)

    for path in requirement_files:
        integration = os.path.basename(os.path.dirname(path))
        print(f"Installing dependencies for '{integration}' from {path}")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", path]
        )
        if result.returncode != 0:
            sys.exit(
                f"Failed to install dependencies for '{integration}'. "
                f"See {path}."
            )

    sys.exit(0)
