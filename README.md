# Git Hooks for Atlassian Stash

This is the git hooks implementation for [Atlassian Bitbucket Server](https://www.atlassian.com/software/bitbucket/server)
(former Stash) External Hooks plugin. This plugin provides an opportunity to add pre-
or post-receive hooks without writting them in Java.

* [External Hooks plugin wiki](https://github.com/ngsru/atlassian-external-hooks/wiki)
* [Githooks doc](https://git-scm.com/docs/githooks) at git-scm.com
* [Atlassian githooks tutorial](https://www.atlassian.com/git/tutorials/git-hooks)

Pre- and post-receive hooks are invoked on the remote repository, when
a git push is done on a local repository.

__Pre-receive hook__ executes just before starting to update refs on the
remote repository, so it’s a good place to enforce any kind of
development policy. Its exit status determines the success or failure
of the update. If you don’t like who is doing the pushing, how the
commit message is formatted, or the changes contained in the commit,
you can simply reject it. While you can’t stop developers from making
malformed commits, you can prevent these commits from entering the
official codebase by rejecting them with pre-receive.

__Post-receive hook__ executes on the remote repository once after all the
refs have been updated. Performing notifications and triggering a
continuous integration system are common use cases for post-receive.

Both pre- and post-receive hooks are invoked once for the receive
operation. Each of them takes no arguments, but for each ref being
updated they receive a line of the format:

```
<old-obj-name> SP <new-obj-name> SP <updated-ref-name> LF
```

on standard input.

## Githooks Framework

We have implemented pre- and post-receive hooks as a collection of
pluggable modules. `githooks.py` serves as an entry point to them,
which loads and runs the modules specified in a configuration file
passed to `githooks.py` via command line. `githooks.py` reads the
standard input and passes <old-obj-name>, <new-obj-name> and
<updated-ref-name> to each plugin being run.

A `githooks.py` plugin implements any desired pre- or post-receive
action, such as indentation check or notification service. A zero
status returned from the plugin indicates success (e.g. the ref being
updated passed the check). A non-zero status from the plugin aborts
the pushing.

If multiple refs are pushed, returning a non-zero status from any of
the plugins for any of the refs aborts pushing all of them.
`githooks.py` executes plugins regardless of their return status,
so all errors are reported at once.

## Git Hooks configuration file

`githooks.py` gets to know which plugins to load and in what setting
to run them from a configuration file that must be passed to
`githooks.py` as the first positional argument.

Configuration file format: dict of plugin basenames without extension
as keys and plugin settings as values (see [Implemented Githooks Plugins](#implemented-githooks-plugins)).

Note: `githooks.py` configuration file must be a valid JSON.

```
{
    <plugin basename without extension>: <plugin settings>,
    ...
}
```

A configuration file for running __py_indent__ and
__line_endings__ plugins with default settings would be:

```
{
    "py_indent": [],
    "line_endings": []
}
```

## Implemented Githooks Plugins

Githooks plugins reside in hooks.d.

Note: plugin settings must be a valid JSON.

### Pre-receive

* __line_endings__ (deny committing files that contain both CRLF and
LF line endings)

Implements checking if any of the modified files contains both CRLF
and LF line endings.

Settings format: None, always runs with an empty list []

* __py_indent__ (basic indentation check in python scripts)

Implements checking if any of the modified python scripts contains
mixed indentation (both tabs and spaces).

Settings format: None, always runs with an empty list []

* __deny_non_ff__ (deny non-fast-forward pushes to specific branches)

Settings format: list of branch regexps
```
[
    "refs/heads/master",
    "refs/heads/release/.*",
    ...
]
```

* __copyright__ (check copyright string)

Checks if file copyright matches at least one of the configured
copyright strings.

Settings format: list of dicts. `start` is a pythonic regexp to check
is the copyright is present in the file. `full` is a full copyright
string to look for in case the copyright presence is detected by the
above check. It can have the currenct year modifier %Y.
```
[
    {
        "start": "Copyright ",
        "full" : "Copyright %Y Roga I Kopyta International"
    },
    ...
]
```
A string formatter for the current year (%Y) might be used.

### Post-receive

* __notify__ (subscribe to some paths via .gitattributes and notify of
changes made to those paths on specific branches)

Reports changes made to paths with defined 'owners' attribute. 'owners'
is a list of comma-separated emails. You can specify branches on which
to report changes as a list of python regular expressions that match
those branches. Note that this is a per-repository setting, i.e all
subscribers will get reports from all those branches.

Settings format:
```
[
    "refs/heads/master",
    "refs/heads/release/.*",
    ...
]
```

Report format: Email reports are composed for each subscriber email.
Essentially an email report is a list of new commits in remote repo
where paths for which 'owners' attribute value contains that email
are modified. List of commits comes in a similar to 'git log'
porcelain output. Additionally, the list of modified paths along with
their status is included for each commit.

```
Branch: <branch>
By user: <username>

Commit: <commit hash> (View in Stash, clickable)
Author: <author name> <author email>
Date: <commit date>

    <commit message, trimmed to 100 symbols>

    <status: M, A or D>  <path to file>
    ...

Commit: ...
```

* __email_mention__ (notify users mentioned in commit messages)

Reports commits to users mentioned in commit messages as @username.
`git ci -m 'My cool new feature @someone'` to send this commit to
someone@domain. Domain is specified in githooks.ini.

Settings format: None, always runs with an empty list []

Report format: similar to __notify__'s report, but commit messages
left untrimmed and does not contain lists of modified files.


## Requirements

* [Atlassian Stash/Bitbucket Server](https://www.atlassian.com/software/bitbucket/server)
* Stash/Bitbucket Server compatible [External Hooks plugin](https://marketplace.atlassian.com/plugins/com.ngs.stash.externalhooks.external-hooks/server/overview)
* Python 2.6 or higher

Note: Tested in the following stack:
* CentOS 6
* Atlassian Stash 3.11.1/Bitbucket Server 4.3.2
* External Hooks plugin 2.5-1/3.0-1
* Python 2.6

## Installation and Basic Setup

* Install and configure [Atlassian Stash/Bitbucket Server](https://confluence.atlassian.com/display/STASH0212/Getting+started)
* Install [External Hooks plugin](https://marketplace.atlassian.com/plugins/com.ngs.stash.externalhooks.external-hooks/server/overview)
* To deploy githooks on a Stash server, clone this repo to
External Hooks safe-dir ($STASH_HOME/external-hooks):

```
$ git clone git://github.com/Parallels/githooks.git $STASH_HOME/external-hooks
```

Then, edit `$STASH_HOME/external-hooks/githooks.ini` and put your
githooks configuration files (.conf) in $STASH_HOME/external-hooks/conf
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
; githooks logfile (log/atlassian-stash-githooks.log)
log_file = %(LOGFILE)s
; where to look for .conf files (external-hooks/conf)
conf_dir = %(CONFDIR)s
; where to look for hook scripts (external-hooks/hooks.d)
hooks_dir = %(HOOKSDIR)s
```

* Go to repository Settings -> (Workflow) Hooks. Enable and configure
External Pre Receive and Post Receive Hooks. Set __Executable__ to
`githooks.py` and check 'Look for hooks only in safe dir'. Put the path
to a configuration file in __Positional parameters__; `githooks.py`
expects a path that is relative to conf_dir (githooks.ini).

## Getting Help

If you get an error while using Git Hooks or discover a bug, please
report it on the [issue tracker](https://github.com/Parallels/githooks).

## Development

Run the unittests:
```
$ python -m unittest test
```

To deploy an emprt repository with githooks installed (in $PWD/tmp):

```
$ source make_repo.sh
```

## License and Authors

* Author: Anna Tikhonova <anna.m.tikhonova@gmail.com>
* Author: Konstantin Nazarov <mail@racktear.com>
* Copyright 2016, Parallels IP Holdings GmbH

Licensed under [the MIT License](http://opensource.org/licenses/MIT).
