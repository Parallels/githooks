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


def main():
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

    permit = True

    # Read in each ref that the user is trying to update.
    for line in fileinput.input(remainder):
        old_sha, new_sha, branch = line.strip().split(' ')

        for hook in config:
            if not os.path.exists(os.path.join(hooks_dir, hook + '.py')):
                logging.error("No such hook: '%s'", hook)
                raise RuntimeError("No such hook: '%s'" % hook)
            module = __import__(hook)
            hook_obj = module.Hook(os.getcwd(), config[hook])
            status, messages = hook_obj.check(
                branch, old_sha, new_sha, hookconfig.pusher)

            for message in messages:
                print "[%s]" % branch.replace('refs/heads/', ''), message

            permit = permit and status

    if not permit:
        sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main()
