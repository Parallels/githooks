#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim:ts=4:sw=4:expandtab
#
# ==================================================================
#
# Copyright (c) 2017, Parallels International GmbH
# Released under the terms of MIT license (see LICENSE for details)
#
# ==================================================================
#
'''
rejectmerge: A hook to reject pushes that contain same-branch merge
'''

import logging
from textwrap import wrap
import hookutil


class Hook(object):

    def __init__(self, repo_dir, settings, params):
        self.repo_dir = repo_dir
        self.settings = settings
        self.params = params

    def check(self, branch, old_sha, new_sha):
        logging.debug("Run: branch=%s, old_sha=%s, new_sha=%s",
                      branch, old_sha, new_sha)
        logging.debug("params=%s", self.params)

        # Do not run the hook if the branch is being deleted
        if new_sha == '0' * 40:
            logging.debug("Deleting the branch, skip the hook")
            return True, []

        def print_commit(commit, formatter='\t%s'):
            '''
            Print a commit using a formatter for each new line.
            The default formatter is a signle tabulation.
            '''
            return '\n'.join(
                [formatter % i for i in
                    ["commit %s" % commit['commit'],
                     "Merge: %s %s" % (parentCommits[0][:7], parentCommits[1][:7]),
                     "Author: %s <%s>" % (commit['author_name'], commit['author_email']),
                     "Date:   %s" % commit['date']] +
                    [""] + # Add a newline
                    wrap(commit['message'], width=120) +
                    [""]
                ])

        permit = True

        log = hookutil.parse_git_log(self.repo_dir, branch, old_sha, new_sha, this_branch_only=False)

        messages = []
        for commit in log:
            # Parse commit parents
            cmd = ['git', 'rev-list', '--parents', '-n', '1', commit['commit']]
            _, out, _ = hookutil.run(cmd, self.repo_dir)
            parentCommits = out.strip().split(' ')[1:]

            # Skip commit if it is not a merge commit
            if len(parentCommits) < 2:
                continue

            logging.debug("Found merge %s, parents: %s %s", commit['commit'][:7], parentCommits[0][:7], parentCommits[1][:7])

            # Find branches that contain parent commits
            parentBranches = []
            for parentCommit in parentCommits:
                cmd = ['git', 'branch', '--contains', parentCommit]
                _, out, _ = hookutil.run(cmd, self.repo_dir)
                if not out:
                    parentBranches.append(branch.replace('refs/heads/', ''))
                else:
                    parentBranches += [br.replace("* ", "") for br in out.strip().split('\n')]

            if len(set(parentBranches)) > 1:
                continue

            mergedBranch = parentBranches[0]
            logging.debug("All parents are on branch '%s'", mergedBranch)

            # First parent must be on the destination branch
            firstParent = parentCommits[0]
            cmd = ['git', 'branch', '--contains', firstParent]
            _, out, _ = hookutil.run(cmd, self.repo_dir)

            if not out.startswith('* '):
                permit = False
                text = '\n'.join(
                    ["Merging a remote branch onto a local branch is prohibited when updating the remote with that local branch.",
                     "",
                     print_commit(commit)] +
                    wrap("You must remove this merge by updating your local branch properly. Please rebase on top of the remote branch:", width=120) +
                    ["",
                     "\tgit pull --rebase origin %s" % mergedBranch,
                     ""])
                messages += [{'at': commit['commit'], 'text': text}]

                logging.info("%s is same-branch merge, permit = %s", commit['commit'][:7], permit)

        logging.debug("Permit: %s", permit)

        return permit, messages
