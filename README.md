# githooks

Hooks are ordinary scripts that git executes when certain events occur in
the repository. For more information on hooks see [Server-side hooks tutorial](https://ru.atlassian.com/git/tutorials/git-hooks/server-side-hooks).

githooks.py implements pre-receive and post-receive git hooks for Stash
External Hooks plugin.

## What is in

* githooks.py: An entry point to githooks, executes scripts from hooks.d/
* hooks.d/: A place for hook scrpits
* make_repo.sh: A script to deploy the hooks in a test repo
* pre-receive.conf.sample
* post-receive.conf.sample: Configuration files used by make_repo.sh
* test.py
* hook_fixture.py: unittests

## Requirements

* python >= 2.6.6
* git

## Usage

* Install External Hooks Stash plugin

* Enable and configure External Pre Receive and Post Receive Hooks.
These hooks mirror the behavior of git pre- and post-receive hooks.

Set __Executable__ to `githooks.py`. Check 'Look for hooks only in safe dir'.
Put a path to a configuration file in __Positional parameters__ (githooks.py
expects a path that is relative to safe-dir/conf).
