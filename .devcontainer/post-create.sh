#!/bin/bash
# Post-installation script

make install-env
git config --global --add safe.directory '/workspaces/*'
