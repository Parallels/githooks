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
py_indent: A hook to check python scripts indentation
'''

import logging
import hookutil


class Hook(object):

    def __init__(self, repo_dir, settings, params):
        self.repo_dir = repo_dir
        self.settings = settings
        self.params = params

    def check(self, branch, old_sha, new_sha):
        logging.debug("branch='%s', old_sha='%s', new_sha='%s', params='%s'",
                      branch, old_sha, new_sha, self.params)
        permit = True

        # Do not run the hook if the branch is being deleted
        if new_sha == '0' * 40:
            logging.debug("Deleting the branch, skip the hook")
            return True, []

        # Before the hook is run git has already created
        # a new_sha commit object

        log = hookutil.parse_git_log(self.repo_dir, branch, old_sha, new_sha)

        messages = []
        for commit in log:
            modfiles = hookutil.parse_git_show(self.repo_dir, commit['commit'], ['.py'])

            def has_mixed_indent(file_contents):
                '''
                Check if file lines start with tabs and spaces
                file_contents = open(file).read()
                '''
                has_tab = False
                has_space = False
                for line in file_contents.split('\n'):
                    if line.startswith('\t'):
                        has_tab = True
                    elif line.startswith(' '):
                        has_space = True
                    if has_tab and has_space:
                        return True
                return False

            # Get the files from the repo and check indentation.
            for modfile in modfiles:
                # Skip deleted files
                if modfile['status'] == 'D':
                    logging.debug("Deleted '%s', skip", modfile['path'])
                    continue

                cmd = ['git', 'show', modfile['new_blob']]
                _, file_contents, _ = hookutil.run(cmd, self.repo_dir)

                permit_py_indent = not has_mixed_indent(file_contents)
                if not permit_py_indent:
                    messages.append({'at': commit['commit'],
                        'text': "Error: file '%s' has mixed indentation" % modfile['path']})

                permit = permit and permit_py_indent
                logging.debug("modfile='%s', permit='%s'", modfile['path'], permit)

        return permit, messages
