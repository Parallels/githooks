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

        # Before the hook is run git has already created
        # a new_sha commit object

        # Get the new_sha diff and parse modified files from it
        if old_sha == '0000000000000000000000000000000000000000':
            old_sha = hookutil.git_empty_tree()
        cmd = ['git', 'diff', '-U0', old_sha, new_sha]
        ret, diff, err = hookutil.run(cmd, self.repo_dir)
        if ret != 0:
            raise RuntimeError(err)

        diff_dict = hookutil.parse_diff(diff)

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
        for modfile in diff_dict:
            text_attr = hookutil.get_attr(
                self.repo_dir, new_sha, modfile, 'text')

            # Attr 'text' enables eol normalization, so
            # the file won't have crlf when the attr is set
            if text_attr == 'unspecified':

                cmd = ['git', 'show', diff_dict[modfile]]
                ret, file_contents, err = hookutil.run(
                    cmd, self.repo_dir, None)
                if ret != 0:
                    raise RuntimeError(err)

                permit_file = not has_mixed_le(file_contents)
                if not permit_file:
                    messages.append(
                        "Error: file '%s' has mixed line endings" % modfile)

                permit = permit and permit_file
                logging.debug("modfile='%s', permit='%s'", modfile, permit)

        return permit, '\n'.join(messages)
