# xcfg task runner. Recipes are grouped under ./just/*.just.
#
#   just              list every available command, grouped
#   just <cmd>        run a command
#   just --show <cmd> inspect a recipe
#
# Keep recipes thin. Heavy logic belongs in tools/ or the library itself.

set shell := ["bash", "-cu"]

[group('help'), doc('List all commands, grouped')]
default:
    @just --list --unsorted

import 'just/dev.just'
import 'just/qa.just'
import 'just/release.just'
