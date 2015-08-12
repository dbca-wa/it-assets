#!/usr/bin/env python
import os, shutil, subprocess, commands, re, plac
from datetime import datetime
from mercurial import lock
import sys


def prompt(cmd, silent=True):
    if not silent: raw_input(cmd)
    else: print(cmd)
    subprocess.check_call(cmd, shell=True)

def install():
    os.chdir("../")
    prompt("virtualenv --distribute --system-site-packages virtualenv")
    prompt('virtualenv/bin/pip install -i http://hg.dec.wa.gov.au/pypi/simple -r requirements.txt')
    if not os.path.exists("manage.py"):
        shutil.copy("dec_base/templates/manage.py", "manage.py")
        prompt("chmod +x manage.py")
    if not os.path.exists("settings.py"):
        return -1
    prompt("python manage.py createcachetable django_cache", silent=False)
    prompt("python manage.py syncdb --migrate", silent=False)

@plac.annotations(function=("The function to call", 'positional', None, str, None))
def main(function="quickdeploy", quiet=False):
    globals()[function]()

if __name__ == '__main__':
    plac.call(main)
