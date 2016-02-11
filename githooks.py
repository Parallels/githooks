#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim:ts=4:sw=4:expandtab
#
# ==================================================================
#
# Copyright (c) 2016, Parallels IP Holdings GmbH
# Released under the terms of MIT license (see LICENSE for details)
#
# ==================================================================
#
'''
Stash external hooks entry point

Executes hooks from this_file_path/hooks.d as specified in
the configuration file (passed as parameter). Reads stdin and passes
it to each executed hook.

On how to configure external hooks see
https://github.com/ngsru/atlassian-external-hooks/wiki/Configuration
'''

import os
import sys
import json
import fileinput
import logging

encoding = sys.getfilesystemencoding()
this_file_path = os.path.dirname(unicode(__file__, encoding))
hooks_dir = os.path.join(this_file_path, 'hooks.d')
sys.path.append(hooks_dir)
import hookconfig


def load_hooks(config, repo=os.getcwd()):
    hooks = []
    for hook in config:
        try:
            module = __import__(hook)
            hooks.append(module.Hook(repo, config[hook]))
        except ImportError as err:
            message = "Could not load hook: '%s' (%s)" % (hook, str(err))
            logging.error(message)
            raise RuntimeError(message)
    return hooks


if __name__ == '__main__':
    # Set up logging
    logging.basicConfig(format='%(asctime)s %(levelname)s [%(filename)s:%(lineno)d] %(message)s',
                        level=logging.DEBUG,
                        filename=hookconfig.logfile)
    logging.debug("Running in '%s'", os.getcwd())

    config_path = os.path.join(hookconfig.config_dir, sys.argv[1])
    remainder = sys.argv[2:]

    # Look for config files only in safe-dir
    with open(config_path) as f:
        config = json.loads(f.read())
    logging.debug("Loaded config '%s'", config_path)

    hooks = load_hooks(config)

    permit = True

    # Read in each ref that the user is trying to update.
    for line in fileinput.input(remainder):
        old_sha, new_sha, branch = line.strip().split(' ')

        for hook in hooks:
            status, messages = hook.check(
                branch, old_sha, new_sha, hookconfig.pusher)

            for message in messages:
                print "[%s @ %s]: %s" % (branch, message['at'], message['text'])

            permit = permit and status

    if not permit:
        sys.exit(1)

    sys.exit(0)
