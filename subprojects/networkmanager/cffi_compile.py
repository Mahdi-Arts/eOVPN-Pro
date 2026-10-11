"""
eOVPN-Pro CFFI Binding Builder
Builds a CFFI Python extension for the NetworkManager native library.
"""

import argparse
import os
import pathlib

import cffi


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", type=str, required=True)
    parser.add_argument("--header", type=str, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ffi = cffi.FFI()
    workdir = pathlib.Path(args.library).parent
    os.chdir(workdir)
    output = workdir / ("_" + pathlib.Path(args.library).name)
    h_file = pathlib.Path(args.header)

    with open(h_file) as header_fd:
        cdef_source = "\n".join(line for line in header_fd if not line.strip().startswith("#"))
        ffi.cdef(cdef_source)

    ffi.set_source(
        output.stem,
        f'#include "{h_file.name}"',
        libraries=[pathlib.Path(args.library).stem.replace("lib", "")],
        library_dirs=[str(workdir)],
        include_dirs=[str(h_file.parent)],
        extra_link_args=["-Wl,-rpath,$ORIGIN"],
    )

    print("cffi library =>", ffi.compile(target=str(output)))


if __name__ == "__main__":
    main()
