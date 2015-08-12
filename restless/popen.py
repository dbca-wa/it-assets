'''
Simple command line wrappers, aim to be fast and synchronous
Currently contains wrappers for:
    curl
    coffee
    lessc
    stylus

Wrapped commands shouldn't change directory, should be as simple a wrapper 
as possible around commandline arguments that allows a user to call them
synchronously and get output returned easily. listcommands function calls
all known functions if they exist and prints their versions
    ::

    Copyright 2011 Department of Environment & Conservation

    Authors:
     * Adon Metcalfe

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
'''
from __future__ import division, print_function, unicode_literals, absolute_import
import logging
logger = logging.getLogger("log."+__name__)

import os
import re
import signal
import subprocess

def handle_alarm(signum, frame):
    # If the alarm is triggered, we're still in the exec_proc.communicate()
    # call, so use exec_proc.kill() to end the process.
    frame.f_locals['self'].kill()

def communicate(args, stdin=None, nice=0, timeout=0, async=False):
    """
    simple wrapper for subprocess that sets some defaults
    returns stdout, stderr
    :param args: args to be passed to Popen
    :param stdin: input to be passed to stdin
    :param nice: amount to increment nice value by
    :param timeout: timeout for process

    Usage::
    >>> int(communicate(["nice"], nice=20)[0])
    19
    >>> communicate(["tail", "-f", "/etc/hosts"], timeout=1)[0].find("localhost") > -1
    True
    """
    if async:
        # recall self as a daemon if async
        import daemon
        with daemon.DaemonContext():
            communicate(args=args, stdin=stdin, nice=nice, timeout=timeout, async=False)
    assert timeout == 0 or timeout >= 1
    logger.debug("Executing (cwd = {1}):\n{0}".format(" ".join(args), os.getcwd()))
    if timeout != 0:
        signal.signal(signal.SIGALRM, handle_alarm)
    proc = subprocess.Popen(args, bufsize=-1, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=lambda : os.nice(nice))
    if timeout != 0:
        signal.alarm(timeout)
    stdout, stderr = proc.communicate(stdin)
    if timeout != 0:
        signal.alarm(0)
    returncode = proc.returncode
    if returncode not in [0, -9]: # allow success or ran out of cpu time
        error = subprocess.CalledProcessError(returncode, " ".join(args))
        error.stdout, error.stderr = stdout, stderr
        raise error
    return stdout, stderr

def listcommands():
    """
    Lists installed commands

    Usage::
    >>> cmds = listcommands()
    >>> isinstance(cmds, basestring)
    True
    """
    output = []
    for args in [
        ["curl", "--version"],
        ["coffee", "--version"],
        ["lessc", "--version"],
        ["stylus", "--version"],
        ["ogrinfo", "--version"],
        ["ogr2ogr", "--version"],
        ["java", "-version"]]:
        output.append(" ".join(args) + ":")
        try:
            output.append(communicate(args)[0])
        except OSError:
            output.append("Error: '{0}' not found, is it installed?".format(args[0]))
    return "\n".join(output)

def ogr2ogr(src, dest, inputlayer=None, inputsql=None, outputsrs='EPSG:4326', outputlayer='the_layer', 
    outputformat="SQLite", outputgeom="GEOMETRY",
    opts=['-gt', 100000, '-lco', 'PRECISION=NO', '-lco', 'LAUNDER=YES', '-lco', 'GEOMETRY_NAME=the_geom', "-explodecollections"], **kwargs):
    """
    ogr2ogr 1.8.0+ wrapper

    return filename of output file
    :param inputfile: ogr source
    :param outputfile: ogr destination
    :param inputlayer: source layer name
    :param inputsql: ogrsql filter to run against input
    :param outputsrs: output srs
    :param outputlayer: output layer name
    :param outputformat: output format
    :param opts: ogr2ogr extra opts
    :param **kwargs: list of additional args to pass to communicate (e.g. nice, timeout)

    Usage::
    """
    args = ["ogr2ogr", "-f", outputformat, "-a_srs", outputsrs, "-nln", outputlayer]
    basecmd = ('nice -n 19 ogr2ogr -f {outputformat} -a_srs "{targetsrs}" ' +
        '{options} -nln the_layer -nlt {geomtype} -gt 100000 /dev/shm/{shmfile} \'{filename}\' ' +
        '-skipfailures -overwrite ' + sqlorlayername + ' && ' +
        'mv -v /dev/shm/{shmfile} {basename}.{ext}')

def ogrinfo(ogrfile, **kwargs):
    """
    ogrinfo wrapper

    return dict of ogr output
    :param filename: filename to inspect with ogrinfo
    :param **kwargs: list of additional args to pass to communicate (e.g. nice, timeout)

    Usage::
    >>> statuscode, headers, content = curl("http://kens-mgmt-055:8300/dumps/EPP_LAKES_DEP_POLYGON.sqlite", filename="/tmp/EPP_LAKES_DEP_POLYGON.sqlite")
    >>> layerdict = ogrinfo("/tmp/EPP_LAKES_DEP_POLYGON.sqlite")
    >>> layerdict["the_layer"]["properties"]["Geometry"] == "POLYGON"
    True
    """
    args = ['ogrinfo', '-ro', '-so', '-al', ogrfile]
    stdout, stderr = communicate(args, **kwargs)
    driverinfo = stdout.split("\n\n")[0]
    rawlayers = stdout.split("\n\n")[1:]
    layers = dict()
    for layer in rawlayers:
        breakdown = layer.split("\n")
        layername = breakdown[0].replace("Layer name: ", "")
        layers[layername] = {"properties":dict(), "attributes":list()}
        uptoattrs = False
        for line in breakdown:
            if line.find("GEOGCS") > -1:
                uptoattrs = True
                continue
            if not line or line[0] == " " or line.find("Layer SRS WKT") > -1 or line.find("(unknown)") > -1:
                continue
            if uptoattrs and line.find(": ") > -1:
                layers[layername]["attributes"].append(line.split(": ")[0])
            elif line.find(": ") > -1:
                prop, val = line.split(": ")
                if prop == "Geometry":
                    val = val.replace("3D ", "").replace(" ","").upper()
                layers[layername]["properties"][prop] = val
            elif line.find("Column = ") > -1:
                layers[layername]["attributes"].append(line.split("Column = ")[1])
                continue
        layers[layername]["name"] = "{Layer name} ({Geometry})".format(**layers[layername]["properties"])
    return layers

def curl(url, auth="--anyauth --user {login}", login=None, filename=None, method="GET", data=None, datafile=None, headers=[], opts=["--location-trusted"], **kwargs):
    """
    curl wrapper
    
    returns statuscode (int), headers (dict), content/filename
    Filename in the case of file output
    :param url: url to request from
    :param auth: authentication options which will be used if login provided, with {login} string being substituted
    :param login: login info that will be injected and added to params as part of auth string
    :param filename: filename to write output too
    :param method:  HTTP method to use, determines how data will be sent
    :param data: data to send, if this and datafile specified, datafile will be used
    :param datafile: data to pass to curl as a file
    :param opts: list of additional options to pass to curl
    :param **kwargs: list of additional args to pass to communicate (e.g. nice, timeout)

    Usage::
    >>> statuscode, headers, content = curl("http://httpbin.org/get")
    >>> statuscode == 200
    True
    >>> statuscode, headers, content = curl("http://httpbin.org/post", method="POST", data="Futurama rocks!")
    >>> statuscode == 200 and content.find("Futurama rocks!") > -1
    True
    >>> statuscode, headers, content = curl("http://httpbin.org/basic-auth/basic/auth", login="basic:auth")
    >>> statuscode == 200 and content.find('"authenticated": true') > -1
    True
    >>> statuscode, headers, content = curl("http://httpbin.org/headers", headers=["Art-vs-Science: Magic Fountain"])
    >>> statuscode == 200 and content.find("Magic") > -1 and headers.has_key("Content-Type")
    True
    """
    args = ['curl']
    args.append(url)
    args += ["-v", "-s", "-S", "-q"] # log everything to stderr, don't show progress, show errors, ignore curlrc
    if login:
        args += auth.format(login=login).split(" ", 2)
    if filename:
        args += ["-o", filename]
    else:
        args += ["-o", "-"]
    args += ["-X", method]
    if method == "POST":
        args.append("--data-binary")
        if datafile:
            args.append("@"+datafile)
        else:
            args.append(data)
    elif method == "PUT" and datafile:
        args += ["-T", datafile]
    elif method == "PUT":
        args += ["--data-binary", data]
    for header in headers:
        args += ["-H", header]
    args += opts
    # Execute command =)
    stdout, stderr = communicate(args, **kwargs)
    # Get some headers
    headerblock = stderr.split("< \r\n")[-2]
    statusline = re.findall("< (HTTP/.+)\r\n", headerblock)[0]
    protocol, statuscode, statusmessage = statusline.split(" ", 2)
    headers = dict(re.findall(r"< (?P<name>.*?): (?P<value>.*?)\r\n", headerblock))
    if filename:
        return int(statuscode), headers, filename
    return int(statuscode), headers, stdout

