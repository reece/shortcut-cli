# Shortcut Importer

This repo contains source for importing GitHub issues into Shortcut.  There is optional support for ZenHub epic assignments.  Web requests to GitHub and ZenHub are cached in order to work-around API limits. Migrated issues/epics are persisted so that restarts effectively pickup from the last successful migration. (In the event of an error, it's possible that an issue is migrated incompletely, resulting in a near-duplicate on shortcut. You should manually delete the older issue.)

**This code was written as a one-off for my own needs. You should spot-check your own migrations. Good luck.**

## Features

- mapping github to shortcut users
- post-process for zenhub to create epics

## Not supported

- labels
- multiple workflows in shortcut (make these later)

## Installation

There is no pip installation because users will likely need to modify the code.  Instead, follow the developer setup below.

## Developer Setup

Setup like this:

    make devready
    source venv/bin/activate

Code reformatting:

    make reformat

Test:

    make test   # for current environment
    make tox    # for Python 3.9 and Python 3.10

Build:

    git tag 0.0.0
    make build
