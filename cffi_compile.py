"""
eOVPN-Pro CFFI Binding Builder
ساخت بایندینگ CFFI برای کتابخانه‌های بومی C در eOVPN-Pro

Generates a CFFI Python extension (``_<lib>.so``) that wraps a native shared
library using a C header, so Python code can call it directly.
این اسکریپت یک افزونه پایتون (``_<lib>.so``) تولید می‌کند که کتابخانه بومی C
را از طریق فایل هدر در اختیار کد پایتون قرار می‌دهد.
"""

import argparse
import os
import pathlib

import cffi


def parse_args() -> argparse.Namespace:
    """Parses the --library / --header command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", type=str, required=True)
    parser.add_argument("--header", type=str, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    ffi = cffi.FFI()

    # Build the wrapper next to the native library / ساخت ماژول کنار کتابخانه بومی
    workdir = pathlib.Path(args.library).parent
    os.chdir(workdir)

    output = workdir / ("_" + pathlib.Path(args.library).name)
    h_file = pathlib.Path(args.header)

    with open(h_file) as header_fd:
        ffi.cdef(header_fd.read())

    ffi.set_source(
        output.stem,
        f'#include "{h_file.name}"',
        libraries=[pathlib.Path(args.library).stem.replace("lib", "")],
        library_dirs=[str(workdir)],
        # Locate the native library relative to the wrapper at runtime
        # مکان‌یابی کتابخانه بومی نسبت به خود ماژول در زمان اجرا
        extra_link_args=["-Wl,-rpath,$ORIGIN"],
    )

    print("cffi library =>", ffi.compile(target=str(output)))


if __name__ == "__main__":
    main()
