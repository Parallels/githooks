#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim:ts=4:sw=4:expandtab
#
'''
Unit tests for githooks

How it works:

* Create a workspace tmp/ in cwd, set up a remote repo and a local
  repo there.

* Replace temp/remote_repo.git/hooks/update in the remote repo with
  hook_fixture.py. The hook_fixture.py script doesn’t do anything
  but dumps the arguments it is called with to a file (branch and
  2 hashes, old and new).

* Each unit test in test.py modifies the local repo somehow, commits
  the changes and then runs `git push` asynchronously. `git push`
  invokes the update hook (hook_fixture.py) in tmp/remote_repo.git.
  The hook script dumps its arguments to a file tmp/request.json.

* The unit test (test.py) waits until tmp/request.json is written,
  reads it in and removes the file. Then, it instantiates the Hook
  object from the hook module it tests, and performs various testing
  using the data from tmp/request.json.

* When the testing is done, the unit test writes a response file
  tmp/response.json for the update script (the update script waits
  until it is able to read this file). The response file contains
  the testing exit code. The update script reads in the file, removes
  it and returns the exit code to git (asynchronously called from the
  unit test in test.py).
'''


import unittest
import subprocess
import shutil
import os
import multiprocessing
import json
import sys
import logging
from time import sleep

sys.path.append("hooks.d")

import hookutil
import hookconfig

import restrict_branches
import line_endings
import py_indent
import notify

def git(cmd, repo=None):
    if repo:
        return subprocess.check_output(['git', '-C', repo] + cmd,
                                       stderr=subprocess.STDOUT)
    else:
        return subprocess.check_output(['git'] + cmd,
                                       stderr=subprocess.STDOUT)

def git_async(cmd, repo=None):
    def call_git(cmd, repo=None, result=None):
        try:
            result.put([0, git(cmd, repo)])
        except subprocess.CalledProcessError, e:
            result.put([e.returncode, e.output])

    result = multiprocessing.Queue()
    proc = multiprocessing.Process(target=call_git, args=(cmd, repo, result))
    proc.start()

    return [proc, result]

def git_async_result(git_call):
    git_call[0].join()
    result = git_call[1].get()

    if result[0] == 0:
        return result[1]
    else:
        raise subprocess.CalledProcessError(result[0], 'git', result[1])

def write_string(filename, string):
    with open(filename, 'w+') as f:
        f.write(string)


class TestBase(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()
        self.base = os.path.join(self.cwd, 'tmp')

        self.logfile = os.path.splitext(__file__)[0] + '.log'
        logging.basicConfig(format='%(filename)s:%(lineno)d# %(levelname)-8s [%(asctime)s]  %(message)s',
                            level=logging.DEBUG,
                            filename=self.logfile)

        self.cleanUp()

        self.remote_repo = os.path.join(self.base, 'remote_repo.git')
        self.repo = os.path.join(self.base, 'repo')

        os.mkdir(self.base)

        self.__setup_remote_repo()
        self.__setup_local_repo()
        self.__add_remote_repo()

        self.hook_request = os.path.join(self.base, 'request.json')
        self.hook_response = os.path.join(self.base, 'response.json')

        os.environ['STASH_REPO_NAME'] = 'unittest'
        os.environ['STASH_PROJECT_KEY'] = 'TEST'

        os.chdir(self.repo)

    def cleanUp(self):
        base = self.base
        if os.path.isdir(base):
            shutil.rmtree(base)

    def __setup_remote_repo(self):
        git(['init', '--bare', self.remote_repo])
        shutil.copy(os.path.join(self.cwd, 'hook_fixture.py'),
                    os.path.join(self.remote_repo, 'hooks', 'update'))

    def __setup_local_repo(self):
        git(['init', self.repo])
        git(['config', 'push.default', 'simple'], self.repo)

    def __add_remote_repo(self):
        git(['remote', 'add', 'origin', self.remote_repo], self.repo)

    def get_request(self):
        request = self.hook_request

        attempts = 0
        while 1:
            if not os.path.exists(request):
                attempts = attempts + 1
                sleep(0.1)
            else:
                break

            if attempts >= 200:
                raise RuntimeError('Timeout exceeded')

        with open(request) as f:
            data = f.read()

        os.remove(request)
        return json.loads(data)

    def write_response(self, code, data):
        with open(self.hook_response, 'w+') as f:
            f.write(json.dumps([code, data]))

    def tearDown(self):
        os.chdir(self.cwd)
        #self.cleanUp()


class TestBasicHooks(TestBase):

    def test_successful_hook(self):
        write_string('foo.txt', 'data')
        git(['add', 'foo.txt'])
        git(['commit', '-m', 'initial commit'])

        git_call = git_async(['push', '-u', 'origin', 'master'], self.repo)

        request = self.get_request()
        self.write_response(0, 'success')

        git_async_result(git_call)

    def test_failed_hook(self):
        write_string('foo.txt', 'otherdata')
        git(['add', 'foo.txt'])
        git(['commit', '-m', 'initial commit'])

        git_call = git_async(['push', '-u', 'origin', 'master'], self.repo)

        self.get_request()
        self.write_response(1, 'hook_failed')

        with self.assertRaises(subprocess.CalledProcessError) as cm:
            git_async_result(git_call)

        self.assertRegexpMatches(cm.exception.output, ".*hook_failed.*")


class TestRestrictBranches(TestBase):

    def test_deny_branch_create(self):
        '''
        Deny create branches, allow update existing ones
        '''
        write_string('foo.txt', 'data')
        git(['add', 'foo.txt'])
        git(['commit', '-m', 'initial commit'])

        # Try to create master branch
        git_call = git_async(['push', '-u', 'origin', 'master'], self.repo)
        request = self.get_request()

        settings = [{
            "policy": "allow",
            "type"  : "update",
            "branch": ".*",
            "user"  : ".*"
        },
        {
            "policy": "deny",
            "type"  : "create",
            "branch": ".*",
            "user"  : ".*"
        }]
        hook = restrict_branches.Hook(self.remote_repo, settings)
        self.assertFalse(hook.check(request[0], request[1], request[2], "myself")[0])

        # Let git push continue
        self.write_response(0, 'success')
        git_async_result(git_call)

        # Master was created; now try to update it
        write_string('bar.txt', 'data')
        git(['add', 'bar.txt'])
        git(['commit', '-m', 'second commit'])

        git_call = git_async(['push', '-u', 'origin', 'master'], self.repo)
        request = self.get_request()

        self.assertTrue(hook.check(request[0], request[1], request[2], "myself")[0])

        self.write_response(0, 'success')
        git_async_result(git_call)

    def test_deny_branch_update(self):
        '''
        Allow create branches, deny update existing ones
        '''
        write_string('foo.txt', 'data')
        git(['add', 'foo.txt'])
        git(['commit', '-m', 'initial commit'])

        # Try to create master branch
        git_call = git_async(['push', '-u', 'origin', 'master'], self.repo)
        request = self.get_request()

        settings = [{
            "policy": "allow",
            "type"  : "create",
            "branch": ".*",
            "user"  : ".*"
        },
        {
            "policy": "deny",
            "type"  : "update",
            "branch": ".*",
            "user"  : ".*"
        }]
        hook = restrict_branches.Hook(self.remote_repo, settings)
        self.assertTrue(hook.check(request[0], request[1], request[2], "myself")[0])

        # Let git push continue
        self.write_response(0, 'success')
        git_async_result(git_call)

        # Master was created; now try to update it
        write_string('bar.txt', 'data')
        git(['add', 'bar.txt'])
        git(['commit', '-m', 'second commit'])

        git_call = git_async(['push', '-u', 'origin', 'master'], self.repo)
        request = self.get_request()

        self.assertFalse(hook.check(request[0], request[1], request[2], "myself")[0])

        self.write_response(0, 'success')
        git_async_result(git_call)

    def test_deny_root_branch_create(self):
        '''
        Deny create branches in root. Allow only branches feature/* and bugfix/*.
        '''
        write_string('foo.txt', 'data')
        git(['add', 'foo.txt'])
        git(['commit', '-m', 'initial commit'])

        # Try to create branch 'feature-branch'
        git_call = git_async(['push', '-u', 'origin', 'master:feature-branch'], self.repo)
        request = self.get_request()

        settings = [{
            "policy": "deny",
            "type"  : "create",
            "branch": ".*",
            "user"  : ".*"
        },
        {
            "policy": "allow",
            "type"  : "create",
            "branch": "feature/.*",
            "user"  : ".*"
        },
        {
            "policy": "allow",
            "type"  : "create",
            "branch": "bugfix/.*",
            "user"  : ".*"
        }]
        hook = restrict_branches.Hook(self.remote_repo, settings)
        self.assertFalse(hook.check(request[0], request[1], request[2], "myself")[0])

        # Let git push continue
        self.write_response(0, 'success')
        git_async_result(git_call)

        # Try to create branch 'bugfix/branch'
        git_call = git_async(['push', '-u', 'origin', 'master:bugfix/branch'], self.repo)
        request = self.get_request()
        self.assertTrue(hook.check(request[0], request[1], request[2], "myself")[0])
        self.write_response(0, 'success')
        git_async_result(git_call)

    def test_allow_branch_create_user(self):
        '''
        Allow only mary create branches release/*.
        Allow only john and mary update release/* branches.
        '''
        write_string('foo.txt', 'data')
        git(['add', 'foo.txt'])
        git(['commit', '-m', 'initial commit'])

        # Try to create branch 'release/branch' by myself
        git_call = git_async(['push', '-u', 'origin', 'master:release/branch'], self.repo)
        request = self.get_request()

        settings = [{
            "policy": "deny",
            "type"  : "create",
            "branch": "release/.*",
            "user"  : ".*"
        },
        {
            "policy": "deny",
            "type"  : "update",
            "branch": "release/.*",
            "user"  : ".*"
        },
        {
            "policy": "allow",
            "type"  : "create",
            "branch": "release/.*",
            "user"  : "mary"
        },
        {
            "policy": "allow",
            "type"  : "update",
            "branch": "release/.*",
            "user"  : "(john|mary)"
        }]
        hook = restrict_branches.Hook(self.remote_repo, settings)
        self.assertFalse(hook.check(request[0], request[1], request[2], "myself")[0])

        # Let git push continue
        self.write_response(0, 'success')
        git_async_result(git_call)

        # Now mary tries to create branch 'release/another'
        git_call = git_async(['push', '-u', 'origin', 'master:release/another'], self.repo)
        request = self.get_request()
        self.assertTrue(hook.check(request[0], request[1], request[2], "mary")[0])
        self.write_response(0, 'success')
        git_async_result(git_call)

        # Now I try to update branch 'release/another'
        write_string('bar.txt', 'data')
        git(['add', 'bar.txt'])
        git(['commit', '-m', 'second commit'])

        git_call = git_async(['push', '-u', 'origin', 'master:release/another'], self.repo)
        request = self.get_request()
        self.assertFalse(hook.check(request[0], request[1], request[2], "myself")[0])
        self.write_response(0, 'success')
        git_async_result(git_call)

        # Now john tries to update 'release/another'
        write_string('foobar.txt', 'data')
        git(['add', 'foobar.txt'])
        git(['commit', '-m', 'second commit'])

        git_call = git_async(['push', '-u', 'origin', 'master:release/another'], self.repo)
        self.assertTrue(hook.check(request[0], request[1], request[2], "john")[0])
        self.write_response(0, 'success')
        git_async_result(git_call)


class TestLineEndings(TestBase):

    def test_get_attr(self):
        write_string('a.txt', 'data')
        write_string('b.txt', 'data')
        write_string('c.txt', 'data')
        write_string('.gitattributes', 'a.txt binary\nb.txt text')
        git(['add', 'a.txt', 'b.txt', 'c.txt', '.gitattributes'])
        git(['commit', '-m', 'initial commit'])
        git_call = git_async(['push', '-u', 'origin', 'master'], self.repo)
        request = self.get_request()

        self.assertEquals(hookutil.get_attr(self.repo, request[2], 'a.txt', 'binary'),
                          'set')
        self.assertEquals(hookutil.get_attr(self.repo, request[2], 'a.txt', 'text'),
                          'unset')
        self.assertEquals(hookutil.get_attr(self.repo, request[2], 'b.txt', 'binary'),
                          'unspecified')
        self.assertEquals(hookutil.get_attr(self.repo, request[2], 'b.txt', 'text'),
                          'set')
        self.assertEquals(hookutil.get_attr(self.repo, request[2], 'c.txt', 'binary'),
                          'unspecified')
        self.assertEquals(hookutil.get_attr(self.repo, request[2], 'c.txt', 'text'),
                          'unspecified')

        self.write_response(0, 'success')
        git_async_result(git_call)

    def test_successful_hook(self):
        write_string('a.txt', 'data\n')
        write_string('.gitattributes', 'a.txt text')
        git(['add', 'a.txt', '.gitattributes'])
        git(['commit', '-m', 'initial commit'])
        git_call = git_async(['push', '-u', 'origin', 'master'], self.repo)
        request = self.get_request()

        hook = line_endings.Hook(self.remote_repo, [])
        self.assertTrue(hook.check(request[0], request[1], request[2], "myself")[0])

        self.write_response(0, 'success')
        git_async_result(git_call)

    def test_failed_hook(self):
        git(['config', 'core.autocrlf', 'false'])
        write_string('a.txt', 'data\r\n\n')
        write_string('b.txt', 'data\r\n\n')
        # git will normalize eols when attr 'text' is set
        write_string('.gitattributes', 'a.txt text')
        git(['add', 'a.txt', 'b.txt', '.gitattributes'])
        git(['commit', '-m', 'initial commit'])
        git_call = git_async(['push', '-u', 'origin', 'master'], self.repo)
        request = self.get_request()

        hook = line_endings.Hook(self.remote_repo, [])
        self.assertFalse(hook.check(request[0], request[1], request[2], "myself")[0])

        self.write_response(0, 'success')
        git_async_result(git_call)


class TestPyIndent(TestBase):

    def test_successful_hook(self):
        write_string('a.py', 'def main():\n  print\n  return 0\n')
        write_string('b.txt', 'data')

        git(['add', 'a.py', 'b.txt'])
        git(['commit', '-m', 'initial commit'])

        git_call = git_async(['push', '-u', 'origin', 'master'], self.repo)
        request = self.get_request()

        hook = py_indent.Hook(self.remote_repo, [])
        self.assertTrue(hook.check(request[0], request[1], request[2], "myself")[0])

        self.write_response(0, 'success')
        git_async_result(git_call)

    def test_failed_hook(self):
        write_string('a.py', 'def main():\n  print\n\treturn 0\n')

        git(['add', 'a.py'])
        git(['commit', '-m', 'initial commit'])

        git_call = git_async(['push', '-u', 'origin', 'master'], self.repo)
        request = self.get_request()

        hook = py_indent.Hook(self.remote_repo, [])
        self.assertFalse(hook.check(request[0], request[1], request[2], "myself")[0])

        self.write_response(0, 'success')
        git_async_result(git_call)


class TestNotify(TestBase):

    def test_compose_mail(self):
        write_string('a.txt', 'data')
        write_string('b.txt', 'data')
        write_string('.gitattributes', 'a.txt owners=myself@gmail.com,somebody@gmail.com\nb.txt owners=somebody@gmail.com')
        git(['add', 'a.txt', 'b.txt', '.gitattributes'])
        git(['commit', '-m', 'initial commit'])

        git_call = git_async(['push', '-u', 'origin', 'master'], self.repo)
        request = self.get_request()

        hook = notify.Hook(self.remote_repo, [])
        owners = hook.compose_mail(request[0], request[1], request[2], "anon")

        self.assertTrue('myself@gmail.com' in owners)
        text = owners['myself@gmail.com']
        self.assertTrue('<b>Branch:</b> master' in text)
        self.assertTrue('Commit: %s' % request[2] in text)
        self.assertTrue('A  a.txt' in text)

        self.assertTrue('somebody@gmail.com' in owners)
        text = owners['somebody@gmail.com']
        self.assertTrue('<b>Branch:</b> master' in text)
        self.assertTrue('Commit: %s' % request[2] in text)
        self.assertTrue('A  a.txt' in text)
        self.assertTrue('A  b.txt' in text)

        self.write_response(0, 'success')
        git_async_result(git_call)

    def test_only_new_commits(self):
        write_string('a.txt', 'data')
        git(['add', 'a.txt'])
        git(['commit', '-m', 'initial commit'])
        git_call = git_async(['push', '-u', 'origin', 'master:one'], self.repo)
        self.get_request()
        self.write_response(0, 'success')
        git_async_result(git_call)

        write_string('b.txt', 'data')
        git(['add', 'b.txt'])
        git(['commit', '-m', 'second commit'])
        git_call = git_async(['push', '-u', 'origin', 'master:two'], self.repo)
        self.get_request()
        self.write_response(0, 'success')
        git_async_result(git_call)

        write_string('b.txt', 'dat')
        write_string('.gitattributes', '*.txt owners=%s' % 'somebody@gmail.com')
        git(['add', 'b.txt', '.gitattributes'])
        git(['commit', '-m', 'third commit'])
        git_call = git_async(['push', '-u', 'origin', 'master'], self.repo)
        request = self.get_request()

        hook = notify.Hook(self.remote_repo, [])
        owners = hook.compose_mail(request[0], request[1], request[2], "anon")

        self.assertTrue('somebody@gmail.com' in owners)
        self.assertTrue(len(owners) == 1)
        text = owners['somebody@gmail.com']
        self.assertTrue('third commit' in text)
        self.assertTrue('M  b.txt' in text)
        self.assertFalse('initial commit' in text)
        self.assertFalse('second commit' in text)

        self.write_response(0, 'success')
        git_async_result(git_call)

        write_string('c.txt', 'dat')
        git(['add', 'c.txt'])
        git(['commit', '-m', 'forth commit'])
        git_call = git_async(['push', '-u', 'origin', 'master'], self.repo)
        request = self.get_request()

        hook = notify.Hook(self.remote_repo, [])
        owners = hook.compose_mail(request[0], request[1], request[2], "anon")

        self.assertTrue('somebody@gmail.com' in owners)
        text = owners['somebody@gmail.com']
        self.assertTrue('forth commit' in text)
        self.assertTrue('A  c.txt' in text)
        self.assertFalse('initial commit' in text)
        self.assertFalse('second commit' in text)
        self.assertFalse('third commit' in text)

        self.write_response(0, 'success')
        git_async_result(git_call)


    def test_bad_owner(self):
        write_string('a.txt', 'data')
        write_string('.gitattributes', 'a.txt owners=somebody@gmail.com,myself')
        git(['add', 'a.txt', '.gitattributes'])
        git(['commit', '-m', 'initial commit'])

        git_call = git_async(['push', '-u', 'origin', 'master'], self.repo)
        request = self.get_request()

        hook = notify.Hook(self.remote_repo, [])
        with self.assertRaises(RuntimeError) as err:
            hook.compose_mail(request[0], request[1], request[2], "anon")

        self.assertTrue("'myself'" in str(err.exception))

        self.write_response(0, 'success')
        git_async_result(git_call)

    def test_successful_hook(self):
        assert hookconfig.devmail != None, 'please configure devmail and send_from to run this test'

        write_string('a.txt', 'data')
        write_string('b.txt', 'data')
        git(['add', 'a.txt', 'b.txt'])
        git(['commit', '-m', 'initial commit'])
        sleep(1)
        git_call = git_async(['push', '-u', 'origin', 'master:another'], self.repo)
        self.get_request()
        self.write_response(0, 'success')
        git_async_result(git_call)

        write_string('b.txt', 'dat')
        write_string('.gitattributes', '*.txt owners=%s' % hookconfig.devmail)
        git(['add', 'b.txt', '.gitattributes'])
        git(['commit', '-m', 'second commit'])
        sleep(1)

        write_string('a.txt', 'dat')
        git(['add', 'a.txt'])
        # Test long commit message trimming
        mes = ' length over one hundred symbols'
        git(['commit', '-m', 'third commit' + mes + mes+ mes])

        git_call = git_async(['push', '-u', 'origin', 'master'], self.repo)
        request = self.get_request()

        hook = notify.Hook(self.remote_repo, [])
        _, messages = hook.check(request[0], request[1], request[2], "anon")

        self.assertTrue(messages[0] == 'Notified users %s' % hookconfig.devmail)

        self.write_response(0, 'success')
        git_async_result(git_call)


if __name__ == '__main__':
    unittest.main()
