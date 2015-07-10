#!/bin/bash

set -e -x -u

cd /tmp/src

## copy over our skel dir, replacing anything that was put in place by RPMs
tar -c -C skel -f - . | tar -xf - -C /

yum install -y centos-release-SCL git

## post-SCL installation
yum install -y python27

export LD_LIBRARY_PATH="$( scl enable python27 'echo ${LD_LIBRARY_PATH}' )"
export PATH="$( scl enable python27 'echo ${PATH}' )"
export PKG_CONFIG_PATH="$( scl enable python27 'echo ${PKG_CONFIG_PATH}' )"

easy_install-2.7 pip==7.1.0
pip2.7 install -r /post_by_email/requirements.txt

mkdir -p /var/log/post-by-email
chown nobody:nobody /var/log/post-by-email

## cleanup
cd /
yum clean all
rm -rf /var/tmp/yum-root* /tmp/src
