# Shortcut CLI

This repo provides a command line client for the [Shortcut](https://shortcut.com/) [API](https://shortcut.com/api/rest/v3).

**This code was written as a one-off for my own needs. You should spot-check your own migrations. Good luck.**

## Goals and Features

- Configure Shortcut projects, teams/groups, technical areas via yaml config file
- Migrate GitHub issues to Shortcut stories, with optional user mapping, team assignments (based on repo), and support for ZenHub Epics.
- Rate limiting and web request caching to mitigate API limits.
- Restartable migration in the event of errors.

## Not supported (yet)

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
