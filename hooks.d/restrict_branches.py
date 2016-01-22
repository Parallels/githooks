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
restrict_branches: A hook to restrict commits to specific branches

Use case: you have product release branches, that should only be
created by product owners or build engineers. Developers should not
be able to create release/* branches.

Another use case: you want to restrict development to specific paths
like feature/* or bugfix/*, and deny creating branches on top level
to prevent pollution.

Settings format:
[
    {
        "policy": "allow/deny",
        "type": "create/update",
        "branch": "<branch regex>",
        "pusher": "<pusher regex>"
    },
    ...
]

The rules are applied from top to bottom.

You can create either whitelist or blacklist rules. The default is to
deny everything, so everything will be blocked if you create an empty
list.

So there are 2 basic options:
* Start with empty list and then add "allow" rules
* Create a wildcard "allow" rule that matches everything and then add
"deny" rules to restrict specific locations.
'''

import re
import logging
import hookutil


class Hook(object):

    def __init__(self, repo_dir, settings):
        self.repo_dir = repo_dir
        self.settings = settings

    def check(self, branch, old_sha, new_sha, pusher):
        logging.debug("branch='%s', old_sha='%s', new_sha='%s', pusher='%s'",
                      branch, old_sha, new_sha, pusher)
        permit = False

        # Check if the branch being pushed is new
        is_new_branch = False
        cmd = ['git', 'rev-parse', branch]
        ret, _, _ = hookutil.run(cmd, self.repo_dir)

        if ret != 0:
            is_new_branch = True

        branch = branch.replace('refs/heads/', '')

        for rule in self.settings:
            # Check policy
            if 'policy' not in rule:
                logging.warning("'policy' not in rule, skip")
                continue
            policy = rule['policy']
            if policy != 'allow' and policy != 'deny':
                logging.warning(
                    "'policy' set to '%s'; must be either 'allow' or 'deny', skip", policy)
                continue

            # Check rule type
            if 'type' not in rule:
                logging.warning("'type' not in rule, skip")
                continue
            rule_type = rule['type']
            if rule_type != 'create' and rule_type != 'update':
                logging.warning(
                    "'type' set to '%s'; must be either 'allow' or 'deny', skip", rule_type)
                continue

            # Check branch regular expression
            try:
                branch_re = re.compile(rule['branch'])
            except re.error:
                logging.warning("Branch regexp '%s' does not compile, skip", rule['branch'])
                continue
            branch_match = branch_re.match(branch)

            # Check pusher regular expression
            try:
                user_re = re.compile(rule['user'])
            except re.error:
                logging.warning("User regexp '%s' does not compile, skip", rule['user'])
                continue
            pusher_match = user_re.match(pusher)

            if not branch_match:
                logging.debug("Branch '%s' does not match '%s', skip", branch, rule['branch'])
                continue

            if not pusher_match:
                logging.debug("Pusher '%s' does not match '%s', skip", pusher, rule['user'])
                continue

            if is_new_branch and rule_type == 'create':
                if policy == 'allow':
                    permit = True
                elif policy == 'deny':
                    permit = False

            if not is_new_branch and rule_type == 'update':
                if policy == 'allow':
                    permit = True
                elif policy == 'deny':
                    permit = False

            logging.debug("is_new_branch='%s', rule_type='%s', policy='%s', permit='%s'",
                          is_new_branch, rule_type, policy, permit)

        messages = []

        if not permit:
            rule_type = 'create' if is_new_branch else 'update'
            messages.append(
                "Error: You have no permission to %s branch '%s'" % (rule_type, branch))

        return permit, messages
