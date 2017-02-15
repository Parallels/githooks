#!/bin/bash
# -*- coding: utf-8 -*-
# vim:ts=4:sw=4:expandtab
#
#   Deploy test environment for githooks
#
# This script initializes a remote repository in tmp/remote_repo.git
# and deploys githooks in tmp/remote_repo.git/hooks with its
# configuration files in <remote repo>/hooks/conf.
#
# Also, the script initializes a local repository in tmp/repo and sets
# it to track tmp/remote_repo.git.
#


test_root=`pwd`/tmp
rm -rf $test_root
mkdir $test_root


# Init a remote repo.
mkdir $test_root/remote_repo.git

root_dir=$test_root/remote_repo.git/hooks
conf_dir=$root_dir/conf
hooks_dir=$root_dir/hooks.d

git init --bare $test_root/remote_repo.git

mkdir -p $conf_dir
mkdir -p $hooks_dir


# Deploy githooks.
cp githooks.py $root_dir
cp hooks.d/*.py $hooks_dir
chmod +x $root_dir/githooks.py
chmod +x $hooks_dir/*.py

# Create githooks.ini
cat >$root_dir/githooks.ini <<EOL
[notify]
user_name = %(USER)s
base_url = http://STASH
proj_key = TEST
repo_name = test

smtp_server = aspmx.l.google.com
smtp_port = 25
smtp_from =

[email_mention]
user_name = %(USER)s
base_url = http://STASH
proj_key = TEST
repo_name = test

smtp_server = aspmx.l.google.com
smtp_port = 25
smtp_from =

email_domain = gmail.com
EOL

# Copy hook configuration files.
cp `pwd`/pre-receive.conf.sample $conf_dir/pre-receive.conf
cp `pwd`/post-receive.conf.sample $conf_dir/post-receive.conf

echo '#!/bin/bash' > $root_dir/pre-receive
echo "$root_dir/githooks.py pre-receive.conf < /dev/stdin" >> $root_dir/pre-receive
chmod +x $root_dir/pre-receive

echo '#!/bin/bash' > $root_dir/post-receive
echo "$root_dir/githooks.py post-receive.conf < /dev/stdin" >> $root_dir/post-receive
chmod +x $root_dir/post-receive


# Init a local repo.
mkdir $test_root/repo
git init $test_root/repo

git -C $test_root/repo remote add origin $test_root/remote_repo.git
