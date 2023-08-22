#!/usr/bin/env python3.7
# -*- coding: utf-8 -*-

import argparse
from . import __version__
from .util import *
from .pdf_tool import *
from .pdg_tool import *
from .zip_tool import *
from .toggle_bw import *
    
def main():
    parser = argparse.ArgumentParser(prog="BookerPdfTool", description="iBooker PDF tool", formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--version", action="version", version=f"BookerPdfTool version: {__version__}")
    parser.set_defaults(func=lambda x: parser.print_help())
    subparsers = parser.add_subparsers()
    
   
    office2pdf_parser = subparsers.add_parser("fm-office", help="doc/xls/ppt to pdf")
    office2pdf_parser.add_argument("fname", help="file name")
    office2pdf_parser.set_defaults(func=office2pdf_handle)
    
    comp_pdf_parser = subparsers.add_parser("comp", help="compress pdf")
    comp_pdf_parser.add_argument("fname", help="file name")
    comp_pdf_parser.set_defaults(func=comp_pdf)


    ext_pdf_parser = subparsers.add_parser("ext", help="extract odf into images")
    ext_pdf_parser.add_argument("fname", help="file name")
    ext_pdf_parser.add_argument("-d", "--dir", default='.', help="path to save")
    ext_pdf_parser.add_argument("-w", "--whole", action='store_true', default=False, help="whether to clip the whole page")
    ext_pdf_parser.set_defaults(func=ext_pdf)

    pdf2html_parser = subparsers.add_parser("2html", help="convert pdf page to html")
    pdf2html_parser.add_argument("fname", help="file name")
    pdf2html_parser.add_argument("-d", "--dir", default='.', help="path to save")
    pdf2html_parser.set_defaults(func=pdf2html)

    anime4k_auto_parser = subparsers.add_parser("anime4k-auto", help="process imgs with waifu2x")
    anime4k_auto_parser.add_argument("fname", help="file or dir name")
    anime4k_auto_parser.add_argument("-G", "--gpu", action='store_true', help="whether to use GPU")
    anime4k_auto_parser.add_argument("-t", "--threads", help="num of threads", type=int, default=8)
    anime4k_auto_parser.set_defaults(func=anime4k_auto_handle)

    pack_pdf_parser = subparsers.add_parser("pack", help="package images into pdf")
    pack_pdf_parser.add_argument("dir", help="dir name")
    pack_pdf_parser.add_argument("-r", "--regex", help="regex of keyword for grouping")
    pack_pdf_parser.add_argument("--jb2", action='store_true', help="rwhether to generate jb2 encoding pdf")
    pack_pdf_parser.set_defaults(func=pack_pdf)


    toggle_bw_parser = subparsers.add_parser("tog-bw", help="check if image colors reversed and then toggle them")
    toggle_bw_parser.add_argument("fname", help="file or dir name")
    toggle_bw_parser.add_argument("-t", "--threads", type=int, default=8, help="num of thread")
    toggle_bw_parser.add_argument("-s", "--thres", type=int, default=50, help="threshold less than which the color will be regarded as black")
    toggle_bw_parser.set_defaults(func=toggle_bw_handle)

    ck_zip_parser = subparsers.add_parser("crack-zip", help="crack encrypted zip")
    ck_zip_parser.add_argument("fname", help="ZIP fname")
    ck_zip_parser.add_argument("-p", "--pw", default=asset('PwdDic.txt'), help="password dict")
    ck_zip_parser.add_argument("-t", "--threads", type=int, default=8, help="num of threads")
    ck_zip_parser.set_defaults(func=crack_zip)


    pdf_auto_parser = subparsers.add_parser("auto", help="auto process pdf")
    pdf_auto_parser.add_argument("fname", help="pdf fname or dirname")
    pdf_auto_parser.add_argument("-t", "--threads", type=int, default=8, help="num of threads")
    pdf_auto_parser.add_argument("-G", "--gpu", action='store_true', help="whether to use GPU")
    pdf_auto_parser.add_argument("-w", "--whole", action='store_true', default=False, help="whether to clip the whole page")
    pdf_auto_parser.set_defaults(func=pdf_auto_handle)

    pick_scan_parser = subparsers.add_parser("pick-scan", help="pick scanned pdf")
    pick_scan_parser.add_argument("dir", help="dirname of pdfs")
    pick_scan_parser.add_argument("-i", "--imgs-area-rate", type=float, default=0.8, help="rate of imgs area in page area, above which a page will be regarded as scanned")
    pick_scan_parser.add_argument("-s", "--scanned-pg-rate", type=float, default=0.8, help="rate of scanned pages in whole doc, above which a pdf will be regarded as scanned")
    pick_scan_parser.add_argument("-t", "--threads", type=int, default=8, help="num of threads")
    pick_scan_parser.set_defaults(func=pick_scanned_pdf)
    
    pdg2pic_parser = subparsers.add_parser("pdg2pic", help="pdg2pic")
    pdg2pic_parser.add_argument("dir", help="dirname of pdfs")
    pdg2pic_parser.add_argument("-o", "--output-dir", help="output dir")
    pdg2pic_parser.set_defaults(func=pdg2pic)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__": main()