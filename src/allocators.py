"""Default allocators using system libraries"""

import os
import subprocess

maybe_allocators = ["tcmalloc", "jemalloc", "hoard"]

allocators = {"libc": {"cmd_prefix"    : "",
                    "binary_suffix" : "",
                    "LD_PRELOAD"    : "",
                    "color"         : "C1"}}

for i, t in enumerate(maybe_allocators):
    try:
        path = subprocess.run('whereis lib{} | cut -d":" -f2'.format(t),
                              shell=True, stdout=subprocess.PIPE,
                              universal_newlines=True).stdout.strip()

        if path != "":
            allocators[t] = {"cmd_prefix": "", "binary_suffix": "",
                          "LD_PRELOAD": path, "color": "C"+str(i+2)}
    except:
        pass
