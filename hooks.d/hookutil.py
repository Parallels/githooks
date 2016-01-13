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
hookutil: Hook utilities
'''

import subprocess
import tempfile
import os
import sys
import logging
import hookconfig

import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.Utils import formatdate, make_msgid


def run(cmd, exec_dir=os.getcwd(), env=None):
    '''
    Execute a command from 'exec_dir' directory.
    '''
    logging.debug("Run cmd: %s", cmd)
    proc = subprocess.Popen(cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            cwd=exec_dir,
                            env=env)
    out, err = proc.communicate()

    return proc.returncode, out, err


def git_empty_tree():
    '''
    Returns empty git object.
    '''
    obj = '/dev/null'
    if sys.platform == 'win32':
        obj = 'NUL'
    cmd = ['git', 'hash-object', '-t', 'tree', obj]
    ret, obj_hash, err = run(cmd, os.getcwd())
    if ret != 0:
        raise RuntimeError(err)
    return obj_hash.strip()


def get_attr(repo_dir, new_sha, filename, attr):
    '''
    Get git attribute 'attr' of file 'filename'.

    - repo_dir: repository root
    - new_sha: git object hash
    '''
    idx_file = tempfile.mkstemp(suffix='git_index')[1]

    # Create an index from new_sha.
    cmd = ['git', 'read-tree', new_sha, '--index-output', idx_file]
    ret, _, err = run(cmd, repo_dir)
    if ret != 0:
        raise RuntimeError(err)

    # Get the attr only from the index.
    env = os.environ.copy()
    env['GIT_INDEX_FILE'] = idx_file
    cmd = ['git', 'check-attr', '--cached', attr, '--', filename]
    ret, out, err = run(cmd, repo_dir, env)
    if ret != 0:
        raise RuntimeError(err)

    os.remove(idx_file)

    # Parse 'git check-attr' output.
    chunks = [c.strip() for c in out.split(':')]
    assert chunks[0] == filename
    assert chunks[1] == attr
    logging.debug("filename='%s', %s='%s'", filename, attr, chunks[2])

    return chunks[2]


def parse_diff(diff, extension=None):
    '''
    Parse 'git diff' output. Return a dictionary
    of modified files and their blob SHA1s. Keys
    are modified filenames and values their blob
    SHA1s.
    '''

    def extension_match(filepath, extension=None):
        '''
        Check if file extension matches any of the passed.

        - extension: an arrays of extension strings
        '''
        if extension is None:
            return True
        return any(filepath.endswith(e) for e in extension)

    diff_dict = {}
    path = new_blob = None
    for line in diff.splitlines():
        # Parse 'index sha..sha mode'
        if line.startswith('index '):
            new_blob = line.split(' ')[1].split('..')[1]
        elif line.startswith('+++ b/'):
            path = line[6:]
            assert new_blob != None
            assert path not in diff_dict
            diff_dict[path] = new_blob
    return dict([(path, blob) for (path, blob) in diff_dict.items()
                 if extension_match(path, extension)])


def send_mail(mail_to, smtp_from, subject):
    '''
    Connect to the server once and send all mails
    from 'mail_to' dictionary. Contains emails as
    keys and messages to send as values.

    smtp_to: the sender
    subject: subject line, common for all mails
    '''
    if not mail_to:
        logging.debug('No mails to send, mail_to empty')
        return

    smtp_server = hookconfig.smtp_server
    smtp_port = hookconfig.smtp_port

    logging.debug("Connecting to the server '%s:%s'", smtp_server, smtp_port)
    smtp = smtplib.SMTP(smtp_server, smtp_port)
    logging.debug('Connected.')
    smtp.set_debuglevel(0)

    for send_to in mail_to:
        text = mail_to[send_to]

        msg_root = MIMEMultipart('related')
        msg_root['From'] = smtp_from
        msg_root['To'] = send_to
        msg_root['Date'] = formatdate(localtime=True)
        msg_root['Message-ID'] = make_msgid()
        msg_root['Subject'] = subject
        msg_root.preamble = 'This is a multi-part message in MIME format.'

        msg = MIMEMultipart('alternative')
        msg.set_charset('utf-8')

        msg_root.attach(msg)

        # Wrapping text to the simple html header
        text = '<HTML><BODY><div><pre>' + text + '</pre></div></BODY></HTML>'

        # Attaching text to the letter
        msg_text = MIMEText(text.encode(
            'utf-8', 'replace'), 'html', _charset='utf-8')
        msg.attach(msg_text)

        email_file_data = msg_root.as_string()

        smtp.sendmail(smtp_from, send_to, email_file_data)
        logging.debug("Sent outgoing email to '%s'", send_to)

    smtp.close()
