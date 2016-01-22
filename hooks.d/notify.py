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
notify: A hook to notify file owners of any changes made to their files

Files are assigned via .gitattributes:
*.py owners=karl@gmail.com

'owners' can be a list of emails separated by comma
'''

import os
import re
import logging
import hookconfig
import hookutil


class Hook(object):

    def __init__(self, repo_dir, settings):
        self.repo_dir = repo_dir
        self.settings = settings
        try:
            self.repo = os.environ['STASH_REPO_NAME']
            self.proj = os.environ['STASH_PROJECT_KEY']
        except KeyError as key:
            logging.error("%s not in env", key)
            raise RuntimeError("%s not in env" % key)

    def compose_mail(self, branch, old_sha, new_sha, pusher):
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

        # Collect modified files per each owner
        files = {}
        for modfile in diff_dict:
            owners_attr = hookutil.get_attr(
                self.repo_dir, new_sha, modfile, 'owners')
            if owners_attr == 'unspecified' or owners_attr == 'unset':
                continue

            for owner in owners_attr.split(','):
                # Check if owner is a valid email address
                # Skip if owner is pusher
                if hookconfig.get_username(owner) == pusher:
                    logging.warning("Pusher '%s' owns '%s', skip", pusher, modfile)
                    continue

                if owner in files:
                    files[owner].append(modfile)
                else:
                    files[owner] = [modfile]

        link = hookconfig.stash_server + "/projects/%s/repos/%s/commits/%s" % (self.proj, self.repo, new_sha)

        for owner in files:
            text = 'List of modified files:\n'
            for modfile in sorted(files[owner]):
                text += '* %s\n' % modfile
            text += '\n'

            text += 'By user: %s\n' % pusher
            text += '\n'

            text += 'Branch: %s\n' % branch.replace('refs/heads/', '')
            text += '\n'

            text += 'Commit: %s\n' % new_sha
            text += '\n'

            text += 'View in Stash: %s' % link

            logging.debug("Files in mail for '%s': %s", owner, ', '.join(files[owner]))
            files[owner] = text

        if not files:
            logging.debug("No owned files were modified in this commit (new_sha='%s')",
                          new_sha)

        return files

    def check(self, branch, old_sha, new_sha, pusher):
        logging.debug("branch='%s', old_sha='%s', new_sha='%s', pusher='%s'",
                      branch, old_sha, new_sha, pusher)

        mails = self.compose_mail(branch, old_sha, new_sha, pusher)

        messages = []
        if mails:
            hookutil.send_mail(mails, hookconfig.send_from,
                               "%s/%s - Hook notify: Files you own were modified" % (self.proj, self.repo))
            # messages.append("Notified users %s" % ', '.join(mails.keys()))

        return True, messages
