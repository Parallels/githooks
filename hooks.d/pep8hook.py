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
pep8hook: A hook to check python scripts style against PEP8. Uses pycodestyle.
'''

import os
import tempfile
import shutil
import logging
import hookutil

pycodestyle_available = False
try:
    import pycodestyle
    pycodestyle_available = True
except ImportError as err:
    print "Failed to import pycodestyle. Please contact your system administrator. Skipping python style check ..."
    logging.error("%s! %s", err, "Please make sure pycodestyle is installed on the system.")


class Hook(object):
    def __init__(self, repo_dir, settings, params):
        self.repo_dir = repo_dir
        self.settings = settings
        self.params = params


    def check(self, branch, old_sha, new_sha):
        # Return early if pycodestyle is not available
        if not pycodestyle_available:
            return True, []

        logging.debug("Run: branch=%s, old_sha=%s, new_sha=%s",
                      branch, old_sha, new_sha)
        logging.debug("params=%s", self.params)

        # Do not run the hook if the branch is being deleted
        if new_sha == '0' * 40:
            logging.debug("Deleting the branch, skip the hook")
            return True, []

        permit = True

        log = hookutil.parse_git_log(self.repo_dir, branch, old_sha, new_sha, this_branch_only=False)
        for commit in log:
            print "Checking commit %s ..." % commit['commit']

            # Filter python scripts from the files modified in new_sha
            modfiles = hookutil.parse_git_show(self.repo_dir, commit['commit'], ['.py'])

            # Next iteration if there are no modified python scripts in the changeset
            if not modfiles:
                continue

            # Set up a working directory for pycodestyle and fill it with the blobs to be checked
            pep8_workdir = tempfile.mkdtemp(suffix='pep8')

            for modfile in modfiles:
                # Skip deleted files
                if modfile['status'] == 'D':
                    logging.debug("Deleted '%s', skip", modfile['path'])
                    continue

                cmd = ['git', 'show', modfile['new_blob']]
                _, file_contents, _ = hookutil.run(cmd, self.repo_dir)

                file_path = os.path.join(pep8_workdir, modfile['path'])
                assert(not os.path.exists(file_path))

                file_dir = os.path.join(pep8_workdir, os.path.dirname(modfile['path']))
                if not os.path.exists(file_dir):
                    os.makedirs(os.path.join(pep8_workdir, os.path.dirname(modfile['path'])))

                with open(file_path, 'w') as fd:
                    fd.write(file_contents)

            # Get the commit's diff; pycodestyle needs it to report only against modified lines
            cmd = ['git', 'show', commit['commit']]
            _, diff, _ = hookutil.run(cmd, self.repo_dir)

            local_dir = os.curdir
            os.chdir(pep8_workdir)
            # Run pycodestyle in the working directory we have just prepared.
            selected_lines = pycodestyle.parse_udiff(diff, patterns=['*.py'], parent='')

            kwargs = {
                "diff"           : True,
                "paths"          : sorted(selected_lines),
                "selected_lines" : selected_lines,
                "reporter"       : pycodestyle.DiffReport
            }

            kwargs.update(self.settings)
            logging.debug("pycodestyle.StyleGuide(%s)", kwargs)

            pep8style = pycodestyle.StyleGuide(**kwargs)

            report = pep8style.check_files()
            os.chdir(local_dir)

            if report.total_errors:
                permit = False

            # Clean up
            shutil.rmtree(pep8_workdir)

        logging.debug("Permit: %s" % permit)

        return permit, []
