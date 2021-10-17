#!/usr/bin/env python3

import argparse
import logging
import os
import subprocess

from gqlalchemy import Memgraph
from gqlalchemy.transformations import nx_to_cypher
import networkx


WORK_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
MG_HOST = "127.0.0.1"
MG_PORT = 7687


def dot_to_mg_graph(path="file.dot", labels=[]):
    graph = networkx.drawing.nx_pydot.read_dot(path)
    for node in graph.nodes(data=True):
        id, data = node
        data["labels"] = labels
        data["name"] = data["label"].strip("'\"")
    return graph


def is_memgraph_ready(host="127.0.0.1", port=7687):
    try:
        memgraph = Memgraph(host, port)
        memgraph.execute("MATCH (n) RETURN n LIMIT 1;")
    except Exception:
        return False
    return True


def dot_to_memgraph(path="file.dot", labels=[], host="127.0.0.1", port=7687):
    if not is_memgraph_ready():
        logging.warning("Memgraph is not ready.")
        return

    memgraph = Memgraph(host, port)
    for query in nx_to_cypher(dot_to_mg_graph(path, labels)):
        memgraph.execute(query)


def is_cmake_ready():
    try:
        subprocess.run(["cmake", "--version"])
    except Exception:
        print("cmake is not available, please installed it.")
        return False
    return True


def generate_cmake_dot(working_dir, output_file):
    os.chdir(working_dir)
    subprocess.run(["cmake", f"--graphviz={output_file}", ".."])


def generate_pip_dot(working_dir, output_file):
    os.chdir(working_dir)
    with open(output_file, "w") as f:
        subprocess.run(["pipdeptree", "--graph-output", "dot"], stdout=f)


def is_cargo_ready():
    try:
        subprocess.run(["cargo", "--version"], check=True)
    except Exception:
        print("cargo is not available, please installed it.")
        return False

    status = subprocess.run(
        ["cargo", "install", "--list"], check=True, capture_output=True
    )
    if status.returncode != 0:
        print("Check of the cargo-deps failed, check installation of cargo.")
        return False
    if "cargo-deps" in str(status.stdout):
        return True
    else:
        print("cargo-deps is not available, please installed it.")
        return False


def generate_cargo_dot(working_dir, output_file):
    os.chdir(working_dir)
    with open(output_file, "w") as f:
        subprocess.run(["cargo", "deps"], stdout=f)


def dot_to_png(input_file, output_file):
    subprocess.run(["dot", "-Tpng", "-o", output_file, input_file])


def main(args):
    if is_cmake_ready() and args.cpp_dir is not None:
        cppdeps_dot = os.path.join(WORK_DIRECTORY, "cppdeps.dot")
        cppdeps_png = os.path.join(WORK_DIRECTORY, "cppdeps.png")
        generate_cmake_dot(args.cpp_dir, cppdeps_dot)
        dot_to_png(cppdeps_dot, cppdeps_png)
        dot_to_memgraph(cppdeps_dot, ["Cpp"])

    # pipdeptree expects graphviz to be installed "locally", in the same
    # environemnt where the executable (pipdeptree) is located, to analyze
    # external dependencies please install them in the current virtualenv.
    pydeps_dot = os.path.join(WORK_DIRECTORY, "pydeps.dot")
    pydeps_png = os.path.join(WORK_DIRECTORY, "pydeps.png")
    generate_pip_dot(WORK_DIRECTORY, pydeps_dot)
    dot_to_png(pydeps_dot, pydeps_png)
    dot_to_memgraph(pydeps_dot, ["Python"])

    if is_cargo_ready() and args.rust_dir is not None:
        for module in [f.path for f in os.scandir(args.rust_dir) if f.is_dir()]:
            if not os.path.isfile(os.path.join(module, "Cargo.toml")):
                continue
            name = os.path.basename(module)
            rsdeps_dot = os.path.join(WORK_DIRECTORY, "rsdeps_%s.dot" % name)
            rsdeps_png = os.path.join(WORK_DIRECTORY, "rsdeps_%s.png" % name)
            generate_cargo_dot(module, rsdeps_dot)
            dot_to_png(rsdeps_dot, rsdeps_png)
            dot_to_memgraph(rsdeps_dot, ["Rust"])


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(asctime)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="Analyze dependencies.")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean the working directory (dot+png files).",
    )
    parser.add_argument("--cpp-dir", default=None, help="Cpp project build directory.")
    parser.add_argument("--python-dir", default=None, help="Python project directory.")
    parser.add_argument(
        "--rust-dir",
        default=None,
        help="Directory of Rust projects. Points to a directory where there are folders with Cargo.toml files.",
    )
    args = parser.parse_args()

    if args.clean:
        os.chdir(WORK_DIRECTORY)
        subprocess.run("rm *.dot* *.png", shell=True)
    else:
        if is_memgraph_ready(MG_HOST, MG_PORT):
            memgraph = Memgraph(MG_HOST, MG_PORT)
            memgraph.execute("MATCH (n) DETACH DELETE n;")
        main(args)
