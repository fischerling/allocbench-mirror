import atexit
from collections import namedtuple
import copy
import csv
import itertools
import multiprocessing
import os
import pickle
import subprocess
from time import sleep

import matplotlib.pyplot as plt
import numpy as np

import src.globalvars
import src.util
from src.util import print_status, print_error, print_warn
from src.util import print_info0, print_info, print_debug

# This is useful when evaluating strings in the plot functions. str(np.NaN) == "nan"
nan = np.NaN


class Benchmark:
    """Default implementation of most methods allocbench expects from a benchmark"""

    # class member to remember if we are allowed to use perf
    perf_allowed = None

    defaults = {"cmd": "false",
                "args": {},
                "measure_cmd": "perf stat -x, -d",
                "servers": [],
                "allocators": copy.deepcopy(src.globalvars.allocators)}

    @staticmethod
    def terminate_subprocess(proc, timeout=5):
        """Terminate or kill a Popen object"""

        # Skip already terminated subprocess
        if proc.poll() is not None:
            return

        print_info("Terminating subprocess", proc.args)
        proc.terminate()
        try:
            outs, errs = proc.communicate(timeout=timeout)
            print_info("Subprocess exited with ", proc.returncode)
        except subprocess.TimeoutExpired:
            print_error("Killing subprocess ", proc.args)
            proc.kill()
            outs, errs = proc.communicate()

        print_debug("Server Out:", outs)
        print_debug("Server Err:", errs)

    @staticmethod
    def scale_threads_for_cpus(factor=1, min_threads=1, steps=10):
        """Helper to scale thread count to execution units

        Return a list of numbers between start and multiprocessing.cpu_count() * factor
        with len <= steps."""
        max_threads = multiprocessing.cpu_count() * factor

        if steps > max_threads - min_threads + 1:
            return list(range(min_threads, max_threads + 1))

        nthreads = []
        divider = 2
        while True:
            factor = max_threads // divider
            entries = max_threads // factor
            if entries > steps - 1:
                return sorted(list(set([min_threads] + nthreads + [max_threads])))

            nthreads = [(i + 1) * factor for i in range(entries)]
            divider *= 2

    def __str__(self):
        return self.name

    def __init__(self, name):
        """Initialize a benchmark with default members if they aren't set already"""
        self.name = name

        # Set default values
        for k in Benchmark.defaults:
            if not hasattr(self, k):
                setattr(self, k, Benchmark.defaults[k])

        # Set result_dir
        if not hasattr(self, "result_dir"):
            self.result_dir = os.path.abspath(os.path.join(src.globalvars.resdir or "",
                                                           self.name))
        # Set build_dir
        if not hasattr(self, "build_dir"):
            self.build_dir = os.path.abspath(os.path.join(src.globalvars.builddir,
                                                          "benchmarks", self.name))

        self.Perm = namedtuple("Perm", self.args.keys())

        default_results = {"args": self.args,
                           "allocators": self.allocators,
                           "facts": {"libcs": {},
                                     "versions": {}}}
        default_results.update({alloc: {} for alloc in self.allocators})

        if not hasattr(self, "results"):
            self.results = default_results
        # Add default default entrys to self.results if their key is absent
        else:
            for key, default in default_results.items():
                if key not in self.results:
                    self.results[key] = default

        if not hasattr(self, "requirements"):
            self.requirements = []

        print_debug("Creating benchmark", self.name)
        print_debug("Cmd:", self.cmd)
        print_debug("Args:", self.args)
        print_debug("Servers:", self.servers)
        print_debug("Requirements:", self.requirements)
        print_debug("Results dictionary:", self.results)
        print_debug("Results directory:", self.result_dir)

    def save(self, path=None):
        """Save benchmark results to a pickle file"""
        f = path if path else self.name + ".save"
        print_info("Saving results to:", f)
        # Pickle can't handle namedtuples so convert the dicts of namedtuples
        # into lists of dicts.
        save_data = {}
        save_data.update(self.results)
        save_data["stats"] = {}
        for allocator in self.results["allocators"]:
            # Skip allocators without measurements
            if self.results[allocator] == {}:
                continue

            measures = []
            stats = []
            for ntuple in self.iterate_args(args=self.results["args"]):
                measures.append((ntuple._asdict(),
                                 self.results[allocator][ntuple]))

                if "stats" in self.results:
                    stats.append((ntuple._asdict(),
                                  self.results["stats"][allocator][ntuple]))

            save_data[allocator] = measures
            if "stats" in self.results:
                save_data["stats"][allocator] = stats

        with open(f, "wb") as f:
            pickle.dump(save_data, f)

    def load(self, path=None):
        """Load benchmark results from a pickle file"""
        if not path:
            f = self.name + ".save"
        else:
            if os.path.isdir(path):
                f = os.path.join(path, self.name + ".save")
            else:
                f = path

        print_info("Loading results from:", f)
        with open(f, "rb") as f:
            self.results = pickle.load(f)
        # Build new named tuples
        for allocator in self.results["allocators"]:
            d = {}
            for perm, measures in self.results[allocator]:
                d[self.Perm(**perm)] = measures
            self.results[allocator] = d

            d = {}
            if "stats" in self.results:
                for perm, value in self.results["stats"][allocator]:
                    d[self.Perm(**perm)] = value
                self.results["stats"][allocator] = d

        # add eventual missing statistics
        if "stats" not in self.results:
            self.calc_desc_statistics()

    def prepare(self):
        """default prepare implementation raising an error if a requirement is not found"""
        os.environ["PATH"] += f"{os.pathsep}{src.globalvars.builddir}/benchmarks/{self.name}"

        for r in self.requirements:
            exe = src.util.find_cmd(r)
            if exe is not None:
                self.results["facts"]["libcs"][r] = src.facter.libc_ver(executable=exe)
            else:
                raise Exception("Requirement: {} not found".format(r))

    def iterate_args(self, args=None):
        """Iterator over each possible combination of args"""
        if not args:
            args = self.args
        arg_names = sorted(args.keys())
        for p in itertools.product(*[args[k] for k in arg_names]):
            Perm = namedtuple("Perm", arg_names)
            yield Perm(*p)

    def iterate_args_fixed(self, fixed, args=None):
        """Iterator over each possible combination of args containing all fixed values

        self.args = {"a1": [1,2], "a2": ["foo", "bar"]}
        self.iterate_args_fixed({"a1":1}) yields [(1, "foo"), (1, "bar")
        self.iterate_args_fixed({"a2":"bar"}) yields [(1, "bar"), (2, "bar")
        self.iterate_args_fixed({"a1":2, "a2":"foo"}) yields only [(2, "foo")]"""

        for perm in self.iterate_args(args=args):
            p_dict = perm._asdict()
            is_fixed = True
            for arg in fixed:
                if p_dict[arg] != fixed[arg]:
                    is_fixed = False
                    break
            if is_fixed:
                yield perm

    def start_servers(self, env=None, alloc_name="None", alloc={"cmd_prefix": ""}):
        """Start Servers

        Servers are not allowed to deamonize because then they can't
        be terminated with their Popen object."""

        substitutions = {"alloc": alloc_name,
                         "perm": alloc_name,
                         "builddir": src.globalvars.builddir}

        substitutions.update(self.__dict__)
        substitutions.update(alloc)

        for server in self.servers:
            server_name = server.get("name", "Server")
            print_info(f"Starting {server_name} for {alloc_name}")

            server_cmd = src.util.prefix_cmd_with_abspath(server["cmd"])
            server_cmd = "{} {} {}".format(self.measure_cmd,
                                           alloc["cmd_prefix"],
                                           server_cmd)

            server_cmd = server_cmd.format(**substitutions)
            print_debug(server_cmd)

            proc = subprocess.Popen(server_cmd.split(), env=env,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE,
                                      universal_newlines=True)

            # TODO: check if server is up
            sleep(5)

            ret = proc.poll()
            if ret is not None:
                print_debug("Stdout:", proc.stdout.read())
                print_debug("Stderr:", proc.stderr.read())
                raise Exception(f"Starting {server_name} failed with exit code: {ret}")
            server["popen"] = proc
            # Register termination of the server
            atexit.register(Benchmark.shutdown_server, self=self, server=server)

            if not "prepare_cmds" in server:
                continue

            print_info(f"Preparing {server_name}")
            for prep_cmd in server["prepare_cmds"]:
                prep_cmd = prep_cmd.format(**substitutions)
                print_debug(prep_cmd)

                proc = subprocess.run(prep_cmd.split(), universal_newlines=True,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                print_debug("Stdout:", proc.stdout)
                print_debug("Stderr:", proc.stderr)


    def shutdown_server(self, server):
        """Terminate a started server running its shutdown_cmds in advance"""
        if server["popen"].poll() != None:
            return

        server_name = server.get("name", "Server")
        print_info(f"Shutting down {server_name}")

        substitutions = {}
        substitutions.update(self.__dict__)
        substitutions.update(server)

        if "shutdown_cmds" in server:
            for shutdown_cmd in server["shutdown_cmds"]:
                shutdown_cmd = shutdown_cmd.format(**substitutions)
                print_debug(shutdown_cmd)

                proc = subprocess.run(shutdown_cmd.split(), universal_newlines=True,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                print_debug("Stdout:", proc.stdout)
                print_debug("Stderr:", proc.stderr)

        Benchmark.terminate_subprocess(server["popen"])

    def shutdown_servers(self):
        """Terminate all started servers"""
        print_info("Shutting down servers")
        for server in self.servers:
            self.shutdown_server(server)

    def run(self, runs=3):
        """generic run implementation"""
        # check if perf is allowed on this system
        if self.measure_cmd == self.defaults["measure_cmd"]:
            if Benchmark.perf_allowed is None:
                print_info("Check if you are allowed to use perf ...")
                res = subprocess.run(["perf", "stat", "ls"],
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     universal_newlines=True)

                if res.returncode != 0:
                    print_error("Test perf run failed with:")
                    print_debug(res.stderr)
                    Benchmark.perf_allowed = False
                else:
                    Benchmark.perf_allowed = True

            if not Benchmark.perf_allowed:
                raise Exception("You don't have the needed permissions to use perf")

        # save one valid result to expand invalid results
        valid_result = {}

        self.results["facts"]["runs"] = runs

        n = len(list(self.iterate_args())) * len(self.allocators)
        for run in range(1, runs + 1):
            print_status(run, ". run", sep='')

            i = 0
            for alloc_name, alloc in self.allocators.items():
                if alloc_name not in self.results:
                    self.results[alloc_name] = {}

                skip = False

                env = dict(os.environ)
                env["LD_PRELOAD"] = env.get("LD_PRELOAD", "")
                env["LD_PRELOAD"] += " " + f"{src.globalvars.builddir}/print_status_on_exit.so"
                env["LD_PRELOAD"] += " " + f"{src.globalvars.builddir}/sig_handlers.so"
                env["LD_PRELOAD"] += " " + alloc["LD_PRELOAD"]

                if "LD_LIBRARY_PATH" in alloc:
                    env["LD_LIBRARY_PATH"] = env.get("LD_LIBRARY_PATH", "")
                    env["LD_LIBRARY_PATH"] += ":" + alloc["LD_LIBRARY_PATH"]

                try:
                    self.start_servers(alloc_name=alloc_name, alloc=alloc, env=env)
                except Exception as e:
                    print_error(e)
                    print_error("Skipping", alloc_name)
                    skip=True

                # Preallocator hook
                if hasattr(self, "preallocator_hook"):
                    self.preallocator_hook((alloc_name, alloc), run, env)

                # Run benchmark for alloc
                for perm in self.iterate_args():
                    i += 1

                    if perm not in self.results[alloc_name]:
                        self.results[alloc_name][perm] = []

                    if skip:
                        self.results[alloc_name][perm].append({})
                        continue

                    print_info0(i, "of", n, "\r", end='')

                    # Available substitutions in cmd
                    substitutions = {"run": run, "alloc": alloc_name}
                    substitutions.update(self.__dict__)
                    substitutions.update(alloc)
                    if perm:
                        substitutions.update(perm._asdict())
                        substitutions["perm"] = ("{}-"*(len(perm)-1) + "{}").format(*perm)
                    else:
                        substitutions["perm"] = ""

                    cmd_argv = self.cmd.format(**substitutions)
                    cmd_argv = src.util.prefix_cmd_with_abspath(cmd_argv).split()
                    argv = []

                    # Prepend cmd if we are not measuring servers
                    if self.servers == []:
                        prefix_argv = alloc["cmd_prefix"].format(**substitutions).split()
                        if self.measure_cmd != "":
                            measure_argv = self.measure_cmd.format(**substitutions)
                            measure_argv = src.util.prefix_cmd_with_abspath(measure_argv).split()

                            argv.extend(measure_argv)

                        argv.extend([f"{src.globalvars.builddir}/exec", "-p", env["LD_PRELOAD"]])
                        if alloc["LD_LIBRARY_PATH"] != "":
                            argv.extend(["-l", env["LD_LIBRARY_PATH"]])

                        argv.extend(prefix_argv)

                    argv.extend(cmd_argv)

                    cwd = os.getcwd()
                    if hasattr(self, "run_dir"):
                        run_dir = self.run_dir.format(**substitutions)
                        os.chdir(run_dir)
                        print_debug("\nChange cwd to:", run_dir)

                    print_debug("\nCmd:", argv)
                    res = subprocess.run(argv, stderr=subprocess.PIPE,
                                         stdout=subprocess.PIPE,
                                         universal_newlines=True)

                    result = {}

                    if res.returncode != 0 or "ERROR: ld.so" in res.stderr:
                        print()
                        print_debug("Stdout:\n" + res.stdout)
                        print_debug("Stderr:\n" + res.stderr)
                        if res.returncode != 0:
                            print_error("{} failed with exit code {} for {}".format(argv, res.returncode, alloc_name))
                        elif "ERROR: ld.so" in res.stderr:
                            print_error("Preloading of {} failed for {}".format(alloc["LD_PRELOAD"], alloc_name))

                    # parse and store results
                    else:
                        if self.servers == []:
                            if os.path.isfile("status"):
                                # Read VmHWM from status file. If our benchmark
                                # didn't fork the first occurance of VmHWM is from
                                # our benchmark
                                with open("status", "r") as f:
                                    for l in f.readlines():
                                        if l.startswith("VmHWM:"):
                                            result["VmHWM"] = l.split()[1]
                                            break
                                os.remove("status")
                        # TODO: get VmHWM from servers
                        else:
                            result["server_status"] = []
                            for server in self.servers:
                                with open("/proc/{}/status".format(server["popen"].pid), "r") as f:
                                    result["server_status"].append(f.read())

                        # parse perf output if available
                        if self.measure_cmd == self.defaults["measure_cmd"]:
                            csvreader = csv.reader(res.stderr.splitlines(),
                                                   delimiter=',')
                            for row in csvreader:
                                # Split of the user/kernel space info to be better portable
                                try:
                                    result[row[2].split(":")[0]] = row[0]
                                except Exception as e:
                                    print_warn("Exception", e, "occured on", row, "for",
                                          alloc_name, "and", perm)

                        if hasattr(self, "process_output"):
                            self.process_output(result, res.stdout, res.stderr,
                                                alloc_name, perm)

                        # save a valid result so we can expand invalid ones
                        if valid_result is not None:
                            valid_result = result

                    self.results[alloc_name][perm].append(result)

                    if os.getcwd() != cwd:
                        os.chdir(cwd)

                if self.servers != []:
                    self.shutdown_servers()

                if hasattr(self, "postallocator_hook"):
                    self.postallocator_hook((alloc_name, alloc), run)

            print()

        # reset PATH
        os.environ["PATH"] = os.environ["PATH"].replace(f"{os.pathsep}{src.globalvars.builddir}/benchmarks/{self.name}", "")

        # expand invalid results
        if valid_result != {}:
            for allocator in self.allocators:
                for perm in self.iterate_args():
                    for i, m in enumerate(self.results[allocator][perm]):
                        if m == {}:
                            self.results[allocator][perm][i] = {k: np.NaN for k in valid_result}

        self.calc_desc_statistics()

    def calc_desc_statistics(self):
        """Calculate descriptive statistics for each datapoint"""
        allocs = self.results["allocators"]
        self.results["stats"] = {}
        for alloc in allocs:
            # Skip allocators without measurements
            if self.results[alloc] == {}:
                continue

            self.results["stats"][alloc] = {}

            for perm in self.iterate_args(self.results["args"]):
                stats = {s: {} for s in ["min", "max", "mean", "median", "std",
                                         "std_perc",
                                         "lower_quartile", "upper_quartile",
                                         "lower_whisker", "upper_whisker",
                                         "outliers"]}
                for dp in self.results[alloc][perm][0]:
                    try:
                        data = [float(m[dp]) for m in self.results[alloc][perm]]
                    except (TypeError, ValueError) as e:
                        print_debug(e)
                        continue
                    stats["min"][dp] = np.min(data)
                    stats["max"][dp] = np.max(data)
                    stats["mean"][dp] = np.mean(data)
                    stats["median"][dp] = np.median(data)
                    stats["std"][dp] = np.std(data, ddof=1)
                    stats["std_perc"][dp] = stats["std"][dp] / stats["mean"][dp]
                    stats["lower_quartile"][dp], stats["upper_quartile"][dp] = np.percentile(data, [25, 75])
                    trimmed_range = stats["upper_quartile"][dp] - stats["lower_quartile"][dp]
                    stats["lower_whisker"][dp] = stats["lower_quartile"][dp] - trimmed_range
                    stats["upper_whisker"][dp] = stats["upper_quartile"][dp] + trimmed_range
                    outliers = []
                    for d in data:
                        if d > stats["upper_whisker"][dp] or d < stats["lower_whisker"][dp]:
                            outliers.append(d)
                    stats["outliers"][dp] = outliers

                self.results["stats"][alloc][perm] = stats

    ###### Summary helpers ######
    def plot_single_arg(self, yval, ylabel="'y-label'", xlabel="'x-label'",
                        autoticks=True, title="'default title'", filepostfix="",
                        sumdir="", arg="", scale=None, file_ext=src.globalvars.summary_file_ext):

        args = self.results["args"]
        allocators = self.results["allocators"]

        arg = arg or list(args.keys())[0]

        if not autoticks:
            x_vals = list(range(1, len(args[arg]) + 1))
        else:
            x_vals = args[arg]

        for allocator in allocators:
            y_vals = []
            for perm in self.iterate_args(args=args):
                if scale:
                    if scale == allocator:
                        y_vals = [1] * len(x_vals)
                    else:
                        mean = eval(yval.format(**self.results["stats"][allocator][perm]["mean"]))
                        norm_mean = eval(yval.format(**self.results["stats"][scale][perm]["mean"]))
                        y_vals.append(mean / norm_mean)
                else:
                    y_vals.append(eval(yval.format(**self.results["stats"][allocator][perm]["mean"])))

            plt.plot(x_vals, y_vals, marker='.', linestyle='-',
                     label=allocator, color=allocators[allocator]["color"])

        plt.legend(loc="best")
        if not autoticks:
            plt.xticks(x_vals, args[arg])
        plt.xlabel(eval(xlabel))
        plt.ylabel(eval(ylabel))
        plt.title(eval(title))
        plt.savefig(os.path.join(sumdir, ".".join([self.name, filepostfix, file_ext])))
        plt.clf()

    def barplot_single_arg(self, yval, ylabel="'y-label'", xlabel="'x-label'",
                           title="'default title'", filepostfix="", sumdir="",
                           arg="", scale=None, file_ext=src.globalvars.summary_file_ext, yerr=True):

        args = self.results["args"]
        allocators = self.results["allocators"]
        nallocators = len(allocators)

        if arg:
            arg = args[arg]
        elif args.keys():
            arg = args[list(args.keys())[0]]
        else:
            arg = [""]

        narg = len(arg)

        for i, allocator in enumerate(allocators):
            x_vals = list(range(i, narg * (nallocators+1), nallocators+1))
            y_vals = []
            y_errs = None
            if yerr:
                y_errs = []

            for perm in self.iterate_args(args=args):
                if scale:
                    if scale == allocator:
                        y_vals = [1] * len(x_vals)
                    else:
                        mean = eval(yval.format(**self.results["stats"][allocator][perm]["mean"]))
                        norm_mean = eval(yval.format(**self.results["stats"][scale][perm]["mean"]))
                        y_vals.append(mean / norm_mean)
                else:
                    y_vals.append(eval(yval.format(**self.results["stats"][allocator][perm]["mean"])))

                if yerr:
                    y_errs.append(eval(yval.format(**self.results["stats"][allocator][perm]["std"])))

            plt.bar(x_vals, y_vals, width=1, label=allocator, yerr=y_errs,
                    color=allocators[allocator]["color"])

        plt.legend(loc="best")
        plt.xticks(list(range(int(np.floor(nallocators/2)), narg*(nallocators+1), nallocators+1)), arg)
        plt.xlabel(eval(xlabel))
        plt.ylabel(eval(ylabel))
        plt.title(eval(title))
        plt.savefig(os.path.join(sumdir, ".".join([self.name, filepostfix, file_ext])))
        plt.clf()

    def plot_fixed_arg(self, yval, ylabel="'y-label'", xlabel="loose_arg",
                       autoticks=True, title="'default title'", filepostfix="",
                       sumdir="", fixed=[], file_ext=src.globalvars.summary_file_ext, scale=None):

        args = self.results["args"]
        allocators = self.results["allocators"]

        for arg in fixed or args:
            loose_arg = [a for a in args if a != arg][0]

            if not autoticks:
                x_vals = list(range(1, len(args[loose_arg]) + 1))
            else:
                x_vals = args[loose_arg]

            for arg_value in args[arg]:
                for allocator in allocators:
                    y_vals = []
                    for perm in self.iterate_args_fixed({arg: arg_value}, args=args):
                        if scale:
                            if scale == allocator:
                                y_vals = [1] * len(x_vals)
                            else:
                                mean = eval(yval.format(**self.results["stats"][allocator][perm]["mean"]))
                                norm_mean = eval(yval.format(**self.results["stats"][scale][perm]["mean"]))
                                y_vals.append(mean / norm_mean)
                        else:
                            eval_dict = self.results["stats"][allocator][perm]["mean"]
                            eval_str = yval.format(**eval_dict)
                            y_vals.append(eval(eval_str))

                    plt.plot(x_vals, y_vals, marker='.', linestyle='-',
                             label=allocator, color=allocators[allocator]["color"])

                plt.legend(loc="best")
                if not autoticks:
                    plt.xticks(x_vals, args[loose_arg])
                plt.xlabel(eval(xlabel))
                plt.ylabel(eval(ylabel))
                plt.title(eval(title))
                plt.savefig(os.path.join(sumdir, ".".join([self.name, arg,
                            str(arg_value), filepostfix, file_ext])))
                plt.clf()

    def export_facts_to_file(self, comment_symbol, f):
        """Write collected facts about used system and benchmark to file"""
        print(comment_symbol, self.name, file=f)
        print(file=f)
        print(comment_symbol, "Common facts:", file=f)
        for k, v in src.globalvars.facts.items():
            print(comment_symbol, k + ":", v, file=f)
        print(file=f)
        print(comment_symbol, "Benchmark facts:", file=f)
        for k, v in self.results["facts"].items():
            print(comment_symbol, k + ":", v, file=f)
        print(file=f)

    def export_stats_to_csv(self, datapoint, path=None):
        """Write descriptive statistics about datapoint to csv file"""
        allocators = self.results["allocators"]
        args = self.results["args"]
        stats = self.results["stats"]

        if path is None:
            path = datapoint

        path = path + ".csv"

        stats_fields = list(stats[list(allocators)[0]][list(self.iterate_args(args=args))[0]])
        fieldnames = ["allocator", *args, *stats_fields]
        widths = []
        for fieldname in fieldnames:
            widths.append(len(fieldname) + 2)

        # collect rows
        rows = {}
        for alloc in allocators:
            rows[alloc] = {}
            for perm in self.iterate_args(args=args):
                d = []
                d.append(alloc)
                d += list(perm._asdict().values())
                d += [stats[alloc][perm][s][datapoint] for s in stats[alloc][perm]]
                d[-1] = (",".join([str(x) for x in d[-1]]))
                rows[alloc][perm] = d

        # calc widths
        for i in range(0, len(fieldnames)):
            for alloc in allocators:
                for perm in self.iterate_args(args=args):
                    field_len = len(str(rows[alloc][perm][i])) + 2
                    if field_len > widths[i]:
                        widths[i] = field_len

        with open(path, "w") as f:
            headerline = ""
            for i, h in enumerate(fieldnames):
                headerline += h.capitalize().ljust(widths[i]).replace("_", "-")
            print(headerline, file=f)

            for alloc in allocators:
                for perm in self.iterate_args(args=args):
                    line = ""
                    for i, x in enumerate(rows[alloc][perm]):
                        line += str(x).ljust(widths[i])
                    print(line.replace("_", "-"), file=f)

    def export_stats_to_dataref(self, datapoint, path=None):
        """Write descriptive statistics about datapoint to dataref file"""
        stats = self.results["stats"]

        if path is None:
            path = datapoint

        path = path + ".dataref"

        # Example: \drefset{/mysql/glibc/40/Lower-whisker}{71552.0}
        line = "\\drefset{{/{}/{}/{}/{}}}{{{}}}"

        with open(path, "w") as f:
            # Write facts to file
            self.export_facts_to_file("%", f)

            for alloc in self.results["allocators"]:
                for perm in self.iterate_args(args=self.results["args"]):
                    for statistic, values in stats[alloc][perm].items():
                        cur_line = line.format(self.name, alloc,
                                               "/".join([str(p) for p in list(perm)]),
                                               statistic, values[datapoint])
                        # Replace empty outliers
                        cur_line.replace("[]", "")
                        # Replace underscores
                        cur_line.replace("_", "-")
                        print(cur_line, file=f)

    def write_best_doublearg_tex_table(self, evaluation, sort=">",
                                       filepostfix="", sumdir="", std=False):
        args = self.results["args"]
        keys = list(args.keys())
        allocators = self.results["allocators"]

        header_arg = keys[0] if len(args[keys[0]]) < len(args[keys[1]]) else keys[1]
        row_arg = [arg for arg in args if arg != header_arg][0]

        headers = args[header_arg]
        rows = args[row_arg]

        cell_text = []
        for av in rows:
            row = []
            for perm in self.iterate_args_fixed({row_arg: av}, args=args):
                best = []
                best_val = None
                for allocator in allocators:
                    d = []
                    for m in self.results[allocator][perm]:
                        d.append(eval(evaluation.format(**m)))
                    mean = np.mean(d)
                    if not best_val:
                        best = [allocator]
                        best_val = mean
                    elif ((sort == ">" and mean > best_val)
                          or (sort == "<" and mean < best_val)):
                        best = [allocator]
                        best_val = mean
                    elif mean == best_val:
                        best.append(allocator)

                row.append("{}: {:.3f}".format(best[0], best_val))
            cell_text.append(row)

        fname = os.path.join(sumdir, ".".join([self.name, filepostfix, "tex"]))
        with open(fname, "w") as f:
            print("\\documentclass{standalone}", file=f)
            print("\\begin{document}", file=f)
            print("\\begin{tabular}{|", end="", file=f)
            print(" l |" * len(headers), "}", file=f)

            print(header_arg+"/"+row_arg, end=" & ", file=f)
            for header in headers[:-1]:
                print(header, end="& ", file=f)
            print(headers[-1], "\\\\", file=f)

            for i, row in enumerate(cell_text):
                print(rows[i], end=" & ", file=f)
                for e in row[:-1]:
                    print(e, end=" & ", file=f)
                print(row[-1], "\\\\", file=f)
            print("\\end{tabular}", file=f)
            print("\\end{document}", file=f)

    def write_tex_table(self, entries, sort=">",
                        filepostfix="", sumdir="", std=False):
        """generate a latex standalone table from an list of entries dictionaries

        Entries must have at least the two keys: "label" and "expression".
        The optional "sort" key specifies the direction of the order:
            ">" : bigger is better.
            "<" : smaller is better.

        Table layout:

        |    alloc1     |    alloc2    | ....
        ---------------------------------------
        | name1  name2  | ...
        ---------------------------------------
        perm1 | eavl1  eval2  | ...
        perm2 | eval1  eval2  | ...
        """
        args = self.results["args"]
        allocators = self.results["allocators"]
        nallocators = len(allocators)
        nentries = len(entries)
        perm_fields = self.Perm._fields
        nperm_fields = len(perm_fields)

        alloc_header_line =  f"\\multicolumn{{{nperm_fields}}}{{c|}}{{}} &"
        for alloc in allocators:
            alloc_header_line += f"\\multicolumn{{{nentries}}}{{c|}}{{{alloc}}} &"
        alloc_header_line = alloc_header_line[:-1] + "\\\\"

        perm_fields_header = ""
        for field in self.Perm._fields:
            perm_fields_header += f'{field} &'
        entry_header_line = ""
        for entry in entries:
            entry_header_line += f'{entry["label"]} &'
        entry_header_line = perm_fields_header + entry_header_line * nallocators
        entry_header_line = entry_header_line[:-1] + "\\\\"

        fname = os.path.join(sumdir, ".".join([self.name, filepostfix, "tex"]))
        with open(fname, "w") as f:
            print("\\documentclass{standalone}", file=f)
            print("\\usepackage{booktabs}", file=f)
            print("\\usepackage{xcolor}", file=f)
            print("\\begin{document}", file=f)
            print("\\begin{tabular}{|", f"{'c|'*nperm_fields}", f"{'c'*nentries}|"*nallocators, "}", file=f)
            print("\\toprule", file=f)

            print(alloc_header_line, file=f)
            print("\\hline", file=f)
            print(entry_header_line, file=f)
            print("\\hline", file=f)

            for perm in self.iterate_args(args=args):
                values = [[] for _ in entries]
                maxs = [None for _ in entries]
                mins = [None for _ in entries]
                for allocator in allocators:
                    for i, entry in enumerate(entries):
                        expr = entry["expression"]
                        values[i].append(eval(expr.format(**self.results["stats"][allocator][perm]["mean"])))

                # get max and min for each entry
                for i, entry in enumerate(entries):
                    if not "sort" in entry:
                        continue
                    # bigger is better
                    elif entry["sort"] == ">":
                        maxs[i] = max(values[i])
                        mins[i] = min(values[i])
                    # smaller is better
                    elif entry["sort"] == "<":
                        mins[i] = max(values[i])
                        maxs[i] = min(values[i])

                # build row
                row = ""
                perm_dict = perm._asdict()
                for field in perm_fields:
                    row += str(perm_dict[field]) + "&"

                for i, _ in enumerate(allocators):
                    for y, entry_vals in enumerate(values):
                        val = entry_vals[i]

                        # format
                        val_str = str(val)
                        if type(val) == float:
                            val_str = f"{val:.2f}"

                        # colorize
                        if val == maxs[y]:
                            val_str = f"\\textcolor{{green}}{{{val_str}}}"
                        elif val == mins[y]:
                            val_str = f"\\textcolor{{red}}{{{val_str}}}"
                        row += f"{val_str} &"
                #escape _ for latex
                row = row.replace("_", "\_")
                print(row[:-1], "\\\\", file=f)

            print("\\end{tabular}", file=f)
            print("\\end{document}", file=f)
