# Copyright 2018-2019 Florian Fischer <florian.fl.fischer@fau.de>
#
# This file is part of allocbench.
#
# allocbench is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# allocbench is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with allocbench.  If not, see <http://www.gnu.org/licenses/>.
"""Collect facts about the benchmark environment"""

import ctypes
import datetime
import errno
import json
import multiprocessing
import os
import platform
from subprocess import CalledProcessError

from allocbench.globalvars import BUILDDIR
from allocbench.util import print_debug, print_info, print_warn, run_cmd

FACTS = {}

def collect_facts():
    """Collect general facts about the benchmark environment"""
    # Populate allocbench.globalvars.facts on import
    _uname = platform.uname()
    FACTS["hostname"] = _uname.node
    FACTS["system"] = _uname.system
    FACTS["kernel"] = _uname.release
    FACTS["arch"] = _uname.machine
    FACTS["cpus"] = multiprocessing.cpu_count()
    FACTS["LD_PRELOAD"] = os.environ.get("LD_PRELOAD", None)

    with open(os.path.join(BUILDDIR, "ccinfo"), "r") as ccinfo:
        FACTS["cc"] = ccinfo.readlines()[-1][:-1]

    # get commit info from git
    allocbench_version()

    starttime = datetime.datetime.now().isoformat()
    # strip seconds from string
    starttime = starttime[:starttime.rfind(':')]
    FACTS["starttime"] = starttime


def store_facts(path=None):
    """Store facts to file"""
    if not path:
        filename = "facts.json"
    elif os.path.isdir(path):
        filename = os.path.join(path, "facts.json")
    else:
        filename = path

    print_info(f"Saving facts to: {filename}")
    with open(filename, "w") as facts_file:
        json.dump(FACTS, facts_file)


def load_facts(path=None):
    """Load facts from file"""
    if not path:
        filename = "facts"
    else:
        if os.path.isdir(path):
            filename = os.path.join(path, "facts")
        else:
            filename = os.path.splitext(path)[0]

    if os.path.exists(filename + ".json"):
        filename += ".json"
        with open(filename, "r") as facts_file:
            loaded_facts = json.load(facts_file)
    elif os.path.exists(filename + ".save"):
        import pickle
        filename += ".save"
        with open(filename, "rb") as facts_file:
            loaded_facts = pickle.load(facts_file)
    else:
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT),
                                filename)
    FACTS.update(loaded_facts)

    print_info(f"Loading facts from: {filename}")

def allocbench_version():
    "Store and return allocbench version string."""
    if "allocbench" in FACTS:
        return FACTS["allocbench"]

    commit = run_cmd(["git", "rev-parse", "HEAD"], capture=True).stdout[:-1]

    proc = run_cmd(["git", "status", "--porcelain"], capture=True)
    dirty = "-dirty" if proc.stdout != "" else ""

    FACTS["allocbench"] = f"{commit}{dirty}"
    return FACTS["allocbench"]


# Copied from pip.
# https://github.com/pypa/pip/blob/master/src/pip/_internal/utils/glibc.py
# Licensed under MIT.
def glibc_version_string(executable=None):
    "Returns glibc version string, or None if not using glibc."

    # ctypes.CDLL(None) internally calls dlopen(NULL), and as the dlopen
    # manpage says, "If filename is NULL, then the returned handle is for the
    # main program". This way we can let the linker do the work to figure out
    # which libc our process is actually using.
    try:
        process_namespace = ctypes.CDLL(executable)
    except OSError:
        return None

    try:
        gnu_get_libc_version = process_namespace.gnu_get_libc_version
    except AttributeError:
        # Symbol doesn't exist -> therefore, we are not linked to
        # glibc.
        return None

    # Call gnu_get_libc_version, which returns a string like "2.5"
    gnu_get_libc_version.restype = ctypes.c_char_p
    version_str = gnu_get_libc_version()
    # py2 / py3 compatibility:
    if not isinstance(version_str, str):
        version_str = version_str.decode("ascii")

    return version_str


# platform.libc_ver regularly returns completely nonsensical glibc
# versions. E.g. on my computer, platform says:
#
#   ~$ python2.7 -c 'import platform; print(platform.libc_ver())'
#   ('glibc', '2.7')
#   ~$ python3.5 -c 'import platform; print(platform.libc_ver())'
#   ('glibc', '2.9')
#
# But the truth is:
#
#   ~$ ldd --version
#   ldd (Debian GLIBC 2.22-11) 2.22
#
# This is unfortunate, because it means that the linehaul data on libc
# versions that was generated by pip 8.1.2 and earlier is useless and
# misleading. Solution: instead of using platform, use our code that actually
# works.
def libc_ver(executable=None):
    """Return glibc version or platform.libc_ver as fallback"""
    glibc_version = glibc_version_string(executable)
    if glibc_version is None:
        # For non-glibc platforms, fall back on platform.libc_ver
        return platform.libc_ver(executable)

    return ("glibc", glibc_version)


def exe_version(executable, version_flag="--version"):
    """Return version of executable"""
    try:
        proc = run_cmd([executable, version_flag], capture=True)
    except CalledProcessError as err:
        print_warn(f"failed to get version of {executable}")
        print_debug(err.stderr)
        return ""

    return proc.stdout[:-1]