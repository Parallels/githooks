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
line_endings: A hook to deny commiting files with mixed line endings
'''

import logging
import hookutil


class Hook(object):

    def __init__(self, repo_dir, settings):
        self.repo_dir = repo_dir
        self.settings = settings

    def check(self, branch, old_sha, new_sha, pusher):
        logging.debug("branch='%s', old_sha='%s', new_sha='%s', pusher='%s'",
                      branch, old_sha, new_sha, pusher)
        permit = True

        # Do not run the hook if the branch is being deleted
        if new_sha == '0' * 40:
            logging.debug("Deleting the branch, skip the hook")
            return True, []

        # Before the hook is run git has already created
        # a new_sha commit object

        modfiles = hookutil.parse_git_show(self.repo_dir, new_sha)

        def has_mixed_le(file_contents):
            '''
            Check if file contains both lf and crlf
            file_contents = open(file).read()
            '''
            if ('\r\n' in file_contents and
                    '\n' in file_contents.replace('\r\n', '')):
                return True
            return False

        messages = []
        for modfile in modfiles:
            text_attr = hookutil.get_attr(
                self.repo_dir, new_sha, modfile['path'], 'text')

            # Attr 'text' enables eol normalization, so
            # the file won't have crlf when the attr is set
            if text_attr == 'unspecified':

                cmd = ['git', 'show', modfile['new_blob']]
                ret, file_contents, err = hookutil.run(cmd, self.repo_dir)
                if ret != 0:
                    raise RuntimeError(cmd, err)

                permit_file = not has_mixed_le(file_contents)
                if not permit_file:
                    messages.append(
                        "Error: file '%s' has mixed line endings" % modfile['path'])

                permit = permit and permit_file
                logging.debug("modfile='%s', permit='%s'", modfile['path'], permit)

        return permit, messages
