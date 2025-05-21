#!/bin/bash
# Post-installation script

git config --global --add safe.directory '/workspaces/*'
task install-dev-env