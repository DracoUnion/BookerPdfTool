#!/usr/bin/env python3.7
# -*- coding: utf-8 -*-

import argparse
from . import __version__
from . import office_tool, img_tool, html_tool, toggle_bw, zip_tool, pdg_tool, dedup

def main():
    parser = argparse.ArgumentParser(prog="BookerPdfTool", description="iBooker PDF tool", formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--version", action="version", version=f"BookerPdfTool version: {__version__}")
    parser.set_defaults(func=lambda x: parser.print_help())
    subparsers = parser.add_subparsers()

    office_tool.reg_subparser(subparsers)
    img_tool.reg_subparser(subparsers)
    html_tool.reg_subparser(subparsers)
    toggle_bw.reg_subparser(subparsers)
    zip_tool.reg_subparser(subparsers)
    pdg_tool.reg_subparser(subparsers)
    dedup.reg_subparser(subparsers)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__": main()