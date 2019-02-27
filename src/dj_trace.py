import matplotlib.pyplot as plt
import numpy as np
import os
from urllib.request import urlretrieve
import sys
import re

from src.benchmark import Benchmark

comma_sep_number_re = "(?:\d*(?:,\d*)?)*"
rss_re = "(?P<rss>" + comma_sep_number_re + ")"
time_re = "(?P<time>" + comma_sep_number_re + ")"

cpu_time_re = re.compile("^{} usec across.*threads$".format(time_re))

max_rss_re = re.compile("^{} Kb Max RSS".format(rss_re))
ideal_rss_re = re.compile("^{} Kb Max Ideal RSS".format(rss_re))

malloc_re = re.compile("^Avg malloc time:\s*{} in.*calls$".format(time_re))
calloc_re = re.compile("^Avg calloc time:\s*{} in.*calls$".format(time_re))
realloc_re = re.compile("^Avg realloc time:\s*{} in.*calls$".format(time_re))
free_re = re.compile("^Avg free time:\s*{} in.*calls$".format(time_re))


class Benchmark_DJ_Trace(Benchmark):
    def __init__(self):
        self.name = "dj_trace"
        self.descrition = """This benchmark uses the workload simulator written
                             by DJ Delorie to simulate workloads provided by
                             him under https://delorie.com/malloc. Those
                             workloads are generated from traces of real
                             aplications and are also used by delorie to
                             measure improvements in the glibc allocator."""

        self.cmd = "trace_run{binary_suffix} dj_workloads/{workload}.wl"
        self.measure_cmd = ""

        self.args = {
                        "workload": [
                                        "389-ds-2",
                                        "dj",
                                        "dj2",
                                        "mt_test_one_alloc",
                                        "oocalc",
                                        "qemu-virtio",
                                        "qemu-win7",
                                        "proprietary-1",
                                        "proprietary-2",
                                      ]
                    }
        self.results = {
                        "389-ds-2": {
                            "malloc": 170500018, "calloc": 161787184,
                            "realloc": 404134, "free": 314856324,
                            "threads": 41},
                        "dj": {
                            "malloc": 2000000, "calloc": 200, "realloc": 0,
                            "free": 2003140, "threads": 201},
                        "dj2": {
                            "malloc": 29263321, "calloc": 3798404,
                            "realloc": 122956, "free": 32709054,
                            "threads": 36},
                        "mt_test_one_alloc": {
                            "malloc": 524290, "calloc": 1, "realloc": 0,
                            "free": 594788, "threads": 2},
                        "oocalc": {
                            "malloc": 6731734, "calloc": 38421,
                            "realloc": 14108, "free": 6826686, "threads": 88},
                        "qemu-virtio": {
                            "malloc": 1772163, "calloc": 146634,
                            "realloc": 59813, "free": 1954732, "threads": 3},
                        "qemu-win7": {
                            "malloc": 980904, "calloc": 225420,
                            "realloc": 89880, "free": 1347825, "threads": 6},
                        "proprietary-1": {
                            "malloc": 316032131, "calloc": 5642, "realloc": 84,
                            "free": 319919727, "threads": 20},
                        "proprietary-2": {
                            "malloc": 9753948, "calloc": 4693,
                            "realloc": 117, "free": 10099261, "threads": 19},
                        }

        self.requirements = ["trace_run"]
        super().__init__()

    def prepare(self, verbose=False):
        super().prepare(verbose=verbose)

        def reporthook(blocknum, blocksize, totalsize):
            readsofar = blocknum * blocksize
            if totalsize > 0:
                percent = readsofar * 1e2 / totalsize
                s = "\r%5.1f%% %*d / %d" % (
                    percent, len(str(totalsize)), readsofar, totalsize)
                sys.stderr.write(s)
            else:  # total size is unknown
                sys.stderr.write("\rdownloaded %d" % (readsofar,))

        if not os.path.isdir("dj_workloads"):
            os.mkdir("dj_workloads")

        download_all = None
        wl_sizes = {"dj": "14M", "oocalc": "65M", "mt_test_one_alloc": "5.7M",
                    "proprietary-1": "2.8G", "qemu-virtio": "34M",
                    "proprietary-2": "92M", "qemu-win7": "23M",
                    "389-ds-2": "3.4G", "dj2": "294M"}

        for wl in self.args["workload"]:
            file_name = wl + ".wl"
            file_path = os.path.join("dj_workloads", file_name)
            if not os.path.isfile(file_path):
                if download_all == None:
                    download_all = input(("Download all workloads (~6.7GB)"
                                          " [Y/n] ")) in ["", "Y", "y"]
                if (not download_all and
                    input("want to download {} ({}) [Y/n] ".format(wl, wl_sizes[wl])) not in ["", "Y", "y"]):
                    continue

                if download_all:
                    print("downloading {} ({}) ...".format(wl, wl_sizes[wl]))

                url = "http://www.delorie.com/malloc/" + file_name
                urlretrieve(url, file_path, reporthook)
                sys.stderr.write("\n")

        available_workloads = []
        for wl in self.args["workload"]:
            file_name = wl + ".wl"
            file_path = os.path.join("dj_workloads", file_name)
            if os.path.isfile(file_path):
                available_workloads.append(wl)

        if len(available_workloads) > 0:
            self.args["workload"] = available_workloads
            return True
        
        return False

    def process_output(self, result, stdout, stderr, allocator, perm, verbose):
        def to_int(s):
            return int(s.replace(',', ""))

        regexs = {7: malloc_re, 8: calloc_re, 9: realloc_re, 10: free_re}
        functions = {7: "malloc", 8: "calloc", 9: "realloc", 10: "free"}
        for i, l in enumerate(stdout.splitlines()):
            if i == 2:
                result["cputime"] = to_int(cpu_time_re.match(l).group("time"))
            if i == 3:
                result["Max_RSS"] = to_int(max_rss_re.match(l).group("rss"))
            elif i == 4:
                result["Ideal_RSS"] = to_int(ideal_rss_re.match(l).group("rss"))
            elif i in [7, 8, 9, 10]:
                res = regexs[i].match(l)
                fname = functions[i]
                result["avg_" + fname] = to_int(res.group("time"))

    def summary(self):
        args = self.results["args"]
        allocators = self.results["allocators"]

        # Total times
        for perm in self.iterate_args(args=args):
            for i, allocator in enumerate(allocators):
                d = [float(x["cputime"]) for x in self.results[allocator][perm]]
                y_val = np.mean(d)/1000
                plt.bar([i], y_val, label=allocator, color=allocators[allocator]["color"])

            # ticks_y = ticker.FuncFormatter(lambda x, pos: '{0:g}'.format(x/1000))
            # plt.gca().yaxis.set_major_formatter(ticks_y)

            plt.legend(loc="best")
            plt.ylabel("Zeit in ms")
            plt.title("Gesamte Laufzeit")
            plt.savefig(".".join([self.name, perm.workload, "runtime", "png"]))
            plt.clf()

        # Function Times
        xa = np.arange(0, 6, 1.5)
        for perm in self.iterate_args(args=args):
            for i, allocator in enumerate(allocators):
                x_vals = [x+i/len(allocators) for x in xa]
                y_vals = [0] * 4
                y_vals[0] = np.mean([x["avg_malloc"] for x in self.results[allocator][perm]])
                y_vals[1] = np.mean([x["avg_calloc"] for x in self.results[allocator][perm]])
                y_vals[2] = np.mean([x["avg_realloc"] for x in self.results[allocator][perm]])
                y_vals[3] = np.mean([x["avg_free"] for x in self.results[allocator][perm]])
                plt.bar(x_vals, y_vals, width=0.25, align="center",
                        label=allocator, color=allocators[allocator]["color"])

            plt.legend(loc="best")
            plt.xticks(xa + 1/len(allocators)*2,
                       ["malloc\n" + str(self.results[perm.workload]["malloc"]) + "\ncalls",
                        "calloc\n" + str(self.results[perm.workload]["calloc"]) + "\ncalls",
                        "realloc\n" + str(self.results[perm.workload]["realloc"]) + "\ncalls",
                        "free\n" + str(self.results[perm.workload]["free"]) + "\ncalls"])
            plt.ylabel("Durchschnittliche Zeit in cycles")
            plt.title("Durchscnittliche Laufzeiten der API Funktionen")
            plt.savefig(".".join([self.name, perm.workload, "apitimes", "png"]))
            plt.clf()

        # Memusage
        for perm in self.iterate_args(args=args):
            for i, allocator in enumerate(allocators):
                d = [x["Max_RSS"] for x in self.results[allocator][perm]]
                y_val = np.mean(d)/1000
                plt.bar([i], y_val, label=allocator, color=allocators[allocator]["color"])

            # add ideal rss
            y_val = self.results[list(allocators.keys())[0]][perm][0]["Ideal_RSS"]/1000
            plt.bar([len(allocators)], y_val, label="Ideal RSS")

            # ticks_y = ticker.FuncFormatter(lambda x, pos: '{0:g}'.format(x/1000))
            # plt.gca().yaxis.set_major_formatter(ticks_y)

            plt.legend(loc="best")
            plt.ylabel("Max RSS in MB")
            plt.title("Maximal benötigter Speicher (VmHWM)")
            plt.savefig(".".join([self.name, perm.workload, "rss", "png"]))
            plt.clf()

        # Tables
        for perm in self.iterate_args(args=args):
            # collect data
            d = {allocator: {} for allocator in allocators}
            for i, allocator in enumerate(allocators):
                d[allocator]["time"] = [float(x["cputime"]) for x in self.results[allocator][perm]]
                d[allocator]["rss"] = [x["Max_RSS"] for x in self.results[allocator][perm]]

            times = [np.mean(d[allocator]["time"]) for allocator in allocators]
            tmin = min(times)
            tmax = max(times)

            rss = [np.mean(d[allocator]["rss"]) for allocator in allocators]
            rssmin = min(rss)
            rssmax = max(rss)

            fname = ".".join([self.name, perm.workload, "table.tex"])
            with open(fname, "w") as f:
                print("\\begin{tabular}{| l | l | l |}", file=f)
                print("& Zeit (ms) / $\\sigma$ (\\%) & VmHWM (KB) / $\\sigma$ (\\%) \\\\", file=f)
                print("\\hline", file=f)

                for allocator in allocators:
                    print(allocator, end=" & ", file=f)

                    t = d[allocator]["time"]
                    m = np.mean(t)
                    s = "\\textcolor{{{}}}{{{:.3f}}} / {:.3f}"
                    if m == tmin:
                        color = "green"
                    elif m == tmax:
                        color = "red"
                    else:
                        color = "black"
                    print(s.format(color, m, np.std(t)/m), end=" & ", file=f)

                    t = d[allocator]["rss"]
                    m = np.mean(t)
                    if m == rssmin:
                        color = "green"
                    elif m == rssmax:
                        color = "red"
                    else:
                        color = "black"
                    print(s.format(color, m, np.std(t)/m), "\\\\", file=f)

                print("\end{tabular}", file=f)


dj_trace = Benchmark_DJ_Trace()
