#/bin/bash

set -e

EXTENSION_ID=com.github.pbkhrv.ulauncher-keepassxc
ULAUNCHER_EXT_DIR=~/.local/share/ulauncher/extensions/

# Remove whatever version of this extension is installed
rm -rf ${ULAUNCHER_EXT_DIR}/${EXTENSION_ID}

echo "Done"
