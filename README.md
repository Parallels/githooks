# Git Hooks for Atlassian Stash

This is the git hooks implementation for [Atlassian Bitbucket Server](https://www.atlassian.com/software/bitbucket/server)
(former Stash) External Hooks plugin. This plugin provides an opportunity to add pre-
or post-receive hooks without writting them in Java.

* [External Hooks plugin wiki](https://github.com/ngsru/atlassian-external-hooks/wiki)
* [Githooks doc](https://git-scm.com/docs/githooks) at git-scm.com
* [Atlassian githooks tutorial](https://www.atlassian.com/git/tutorials/git-hooks)

Pre- and post-receive hooks are invoked on the remote repository, when
a git push is done on a local repository.

Pre-receive hook executes just before starting to update refs on the
remote repository, so it’s a good place to enforce any kind of
development policy. Its exit status determines the success or failure
of the update. If you don’t like who is doing the pushing, how the
commit message is formatted, or the changes contained in the commit,
you can simply reject it. While you can’t stop developers from making
malformed commits, you can prevent these commits from entering the
official codebase by rejecting them with pre-receive.

Post-receive hook executes on the remote repository once after all the
refs have been updated. Performing notifications and triggering a
continuous integration system are common use cases for post-receive.

Both pre- and post-receive hooks are invoked once for the receive
operation. Each of them takes no arguments, but for each ref being
updated they receive a line of the format:

```
<old-obj-name> SP <new-obj-name> SP <updated-ref-name> LF
```

on standard input.

We have implemented 4 hook scripts:

* hooks.d/restrict_branches.py (restrict commits to specific branches)
* hooks.d/line_endings.py (deny commiting files with mixed line endings)
* hooks.d/py_indent.py (check basic indentation in python scripts)
* hooks.d/notify.py (notify file owners of any changes made to their files)

and `githooks.py` as an entry point to these scripts. `githooks.py`
executes the hook scripts specified in a configuration file passed via
command line. Then, it reads the standard input line by line and runs
the scripts for each ref being updated. Each script takes the name of
the ref being updated, the old object name and the new object name
stored in the ref as arguments. If multiple refs are pushed, returning
a non-zero status from any of the executed hook scripts for any of the
refs aborts all of them.

## Git Hooks configuration file

`githooks.py` expects the following configuration file format:

```
{
    <script_filename_without_ext>: <hook_settings>,
    ...
}
```

E.g. running __restrict_branches__ and __line_endings__ hook scripts
with default settings requires the following configuration file for
`githooks.py`:

```
{
    "restrict_branches": [],
    "line_endings": []
}
```

*Note:* By default, __restrict_branches__ denies creating and updating
any path for everyone. On hook script settings see below.

With this configuration file, `githooks.py` implements an example
pre-receive hook. An example post-receive hook can be implemented with
the following configuration file:

```
{
    "notify": [],
}
```

## Implemented Hook Scripts

* __hooks.d/restrict_branches.py__: A hook script to restrict commits
to specific branches.

Use case: you have product release branches, that should only be
created by product owners or build engineers. Developers should not be
able to create release/* branches.

Another use case: you want to restrict development to specific paths
like feature/* or bugfix/*, and deny creating branches on top level
to prevent pollution.

Settings format:

```
[
    {
        "policy": "allow/deny",
        "type": "create/update",
        "branch": "<branch regex>",
        "pusher": "<pusher regex>"
    },
    ...
]
```

The rules are applied from top to bottom. You can create either
whitelist or blacklist rules. The default is to deny everything, so
everything will be blocked if you create an empty list. Hence there
are 2 basic options:
  1. Start with empty list and then add "allow" rules,
  2. Create a wildcard "allow" rule that matches everything and then
add "deny" rules to restrict specific locations.

* __hooks.d/line_endings.py__: A hook script for denying commiting
files with mixed line endings

Checks if any of the files modified in a pushed ref contains both CRLF
and LF line endings. Aborts the pushing, if so.

Settings format: None

* __hooks.d/py_indent.py__: A hook script for checking python scripts
indentation

Checks if any of the python scripts modified in a pushed ref are
indented with tabs and spaces. Aborts the pushing, if so.

Settings format: None

* __hooks.d/notify.py__: A hook script for notifying path subscribers
of changes made to those paths

Reports who made the change, the ref and the list of changed files to
the subscribers defined via git attributes.

Putting the following .gitattibutes file in a repository will result in
reporting to karl@gmail.com every pushed commit with changes to *.py
files.

```
*.py owners=karl@gmail.com
```

`owners` can be a list of email addresses separated by comma.

Settings format:
```
[
    "refs/heads/ref_name",
    "refs/tags/tag_name",
    ...
]
```
A list of full ref names where changes are reported, a per-repository
setting.


## Requirements

* [Atlassian Bitbucket Server (Stash)](https://www.atlassian.com/software/bitbucket/server)
* Bitbucket Server (Stash) compatible [External Hooks plugin](https://marketplace.atlassian.com/plugins/com.ngs.stash.externalhooks.external-hooks/server/overview)
* Python 2.6 or higher

*Note:* Tested in the following stack:
* CentOS 6
* Atlassian Stash 3.11.1/Bitbucket Server 4.3.2
* External Hooks plugin 2.5-1/3.0-1
* Python 2.6

## Installation and Basic Setup

* Install and configure [Atlassian Bitbucket Server (Stash)](https://confluence.atlassian.com/display/STASH0212/Getting+started)
* Install [External Hooks plugin](https://marketplace.atlassian.com/plugins/com.ngs.stash.externalhooks.external-hooks/server/overview)
* To deploy githooks on a Stash server, clone this repo to
STASH_HOME/external-hooks:

```
$ git clone git://github.com/Parallels/githooks.git $STASH_HOME/external-hooks
```

Then, edit `$STASH_HOME/external-hooks/githooks.ini` and put your
githooks configuration files in $STASH_HOME/external-hooks/conf
(pre-receive.conf.sample and post-receive.conf.sample demonstrate the
minimal setup). Change the files mode so that the user that runs Stash
(`stash`/`bitbucket` by default) owns the files. Python scripts must
be executable:

```
$ chown -R stash $STASH_HOME/external-hooks
$ chgrp -R stash $STASH_HOME/external-hooks
$ chmod -R 755 $STASH_HOME/external-hooks
```

Note: default githooks layout can be overriden in [DEFAULT] section of
`githooks.ini`:

```
[DEFAULT]
; githooks logfile
log_file = %(LOGFILE)s
; where to look for .conf files
conf_dir = %(CONFDIR)s
; where to look for hook scripts
hooks_dir = %(HOOKSDIR)s
...
```

* Go to repository Settings -> (Workflow) Hooks. Enable and configure
External Pre Receive and Post Receive Hooks. Set __Executable__ to
`githooks.py` and check 'Look for hooks only in safe dir'. Put the path
to a configuration file in __Positional parameters__; `githooks.py`
expects a path that is relative to safe-dir/conf/PROJECT_KEY/REPO_NAME.

*Note:* `githooks.py` is set up for the plugin safe dir STASH_HOME/external-hooks.
If it is different for your Stash/Bitbucket Server instance please report it on the
[issue tracker](https://github.com/Parallels/githooks).

## Getting Help

If you get an error while using Git Hooks or discover a bug, please
report it on the [issue tracker](https://github.com/Parallels/githooks).

## Development

Before running __notify__ hook script unittests, edit SMTP relay
settings and smtp_from email address. This address is used to test
the code that sends notifications via a relay.

To run the unittests:
```
$ python -m unittest test
```

To deploy a repository with githooks installed (in pwd/testroot):

```
$ source make_repo.sh
```

## License and Authors

* Author: Anna Tikhonova <anna.m.tikhonova@gmail.com>
* Author: Konstantin Nazarov <mail@racktear.com>
* Copyright 2016, Parallels IP Holdings GmbH

Licensed under [the MIT License](http://opensource.org/licenses/MIT).
