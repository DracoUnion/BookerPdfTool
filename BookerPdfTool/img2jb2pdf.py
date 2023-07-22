#!/usr/bin/python
# Copyright 2006 Google Inc.
# Author: agl@imperialviolet.org (Adam Langley)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# JBIG2 Encoder
# https://github.com/agl/jbig2enc

import sys
import re
import struct
import os
from os import path
import shutil
from imgyaso import adathres_bts
from .util import *

file = open
# This is a very simple script to make a PDF file out of the output of a
# multipage symbol compression.
# Run ./jbig2 -s -p <other options> image1.jpeg image1.jpeg ...
# python pdf.py output > out.pdf

dpi = 72

class Ref:
    def __init__(self, x):
        self.x = x
    def __bytes__(self):
        return b"%d 0 R" % self.x

class Dict:
    def __init__(self, values = {}):
        self.d = {}
        self.d.update(values)

    def __bytes__(self):
        s = [b'<< ']
        for (x, y) in self.d.items():
          s.append(b'/%s ' % x)
          s.append(y)
          s.append(b"\n")
        s.append(b">>\n")

        return b''.join(s)

global_next_id = 1

class Obj:
    next_id = 1
    def __init__(self, d = {}, stream = None):
        global global_next_id

        if stream is not None:
          d[b'Length'] = b'%d' % len(stream)
        self.d = Dict(d)
        self.stream = stream
        self.id = global_next_id
        global_next_id += 1

    def __bytes__(self):
        s = []
        s.append(bytes(self.d))
        if self.stream is not None:
          s.append(b'stream\n')
          s.append(self.stream)
          s.append(b'\nendstream\n')
        s.append(b'endobj\n')

        return b''.join(s)

class Doc:
    def __init__(self):
        self.objs = []
        self.pages = []

    def add_object(self, o):
        self.objs.append(o)
        return o

    def add_page(self, o):
        self.pages.append(o)
        return self.add_object(o)

    def __bytes__(self):
        a = []
        j = [0]
        offsets = []

        def add(x):
          a.append(x)
          j[0] += len(x) + 1
        add(b'%PDF-1.4')
        for o in self.objs:
          offsets.append(j[0])
          add(b'%d 0 obj' % o.id)
          add(bytes(o))
        xrefstart = j[0]
        a.append(b'xref')
        a.append(b'0 %d' % (len(offsets) + 1))
        a.append(b'0000000000 65535 f ')
        for o in offsets:
          a.append(b'%010d 00000 n ' % o)
        a.append(b'')
        a.append(b'trailer')
        a.append(b'<< /Size %d\n/Root 1 0 R >>' % (len(offsets) + 1))
        a.append(b'startxref')
        a.append(b'%d' % xrefstart)
        a.append(b'%%EOF')

        # sys.stderr.write(bytes(offsets) + "\n")

        return b'\n'.join(a)

def ref(x):
  return b'%d 0 R' % x

def make_jb2_pdf(symtbl, contents):
    doc = Doc()
    doc.add_object(Obj({
        b'Type' : b'/Catalog', 
        b'Outlines' : ref(2), 
        b'Pages' : ref(3),
    }))
    doc.add_object(Obj({
        b'Type' : b'/Outlines', 
        b'Count': b'0'
    }))
    pages = Obj({b'Type' : b'/Pages'})
    doc.add_object(pages)
    symd = doc.add_object(Obj({}, symtbl))
    page_objs = []

    for cont in contents:
        (width, height, xres, yres) = struct.unpack('>IIII', cont[11:27])

        if xres == 0:
            xres = dpi
        if yres == 0:
            yres = dpi

        xobj = Obj({
            b'Type': b'/XObject', 
            b'Subtype': b'/Image', 
            b'Width': b'%d' % width, 
            b'Height': b'%d' % height, 
            b'ColorSpace': b'/DeviceGray',
            b'BitsPerComponent': b'1', 
            b'Filter': b'/JBIG2Decode', 
            b'DecodeParms': b' << /JBIG2Globals %d 0 R >>' % symd.id
        }, cont)
        cont = Obj({}, b'q %f 0 0 %f 0 0 cm /Im1 Do Q' % (float(width * 72) / xres, float(height * 72) / yres))
        resources = Obj({
            b'ProcSet': b'[/PDF /ImageB]',
            b'XObject': b'<< /Im1 %d 0 R >>' % xobj.id
        })
        page = Obj({
            b'Type': b'/Page', 
            b'Parent': b'3 0 R',
            b'MediaBox': b'[ 0 0 %f %f ]' % (float(width * 72) / xres, float(height * 72) / yres),
            b'Contents': ref(cont.id),
            b'Resources': ref(resources.id)
        })
        [doc.add_object(x) for x in [xobj, cont, resources, page]]
        page_objs.append(page)

        pages.d.d[b'Count'] = b'%d' % len(page_objs)
        pages.d.d[b'Kids'] = b'[' + b' '.join([ref(x.id) for x in page_objs]) + b']'

    # print(bytes(doc))
    # open(sys.argv[1] + '.pdf', 'wb').write(bytes(doc))
    return bytes(doc)


def img_to_jb2_pdf(fnames):
    tmpdir = path.join(tempfile.gettempdir(), uuid.uuid4().hex)
    safe_mkdir(tmpdir)
    pref = uuid.uuid4().hex
    # 避免命令行过长
    l = len(str(len(fnames)))
    nfnames = [
        path.join(tmpdir, str(i).zfill(l) + '.png')
        for i in range(len(imgs))
    ]
    for f, nf in zip(fnames, nfnames):
        shutil.copy(f, nf)
    subp.Popen(
        [
            asset('jbig2enc'), 
            '-s', '-p', 
            '-T', '128',
            '-b', path.join(tmpdir, pref), 
            path.join(tmpdir, '*.png'),
        ], shell=True,
    ).communicate()
    symtbl_fname = path.join(tmpdir, pref + '.sym')
    symtbl = open(symtbl_fname, 'rb').read()
    jb2_fnames = [
        path.join(tmpdir, f) 
        for f in os.listdir(tmpdir) 
        if re.search(pref + r'\.\d+$', f)
    ]
    jb2_fnames.sort()
    jb2_contents = [open(f, 'rb').read() for f in jb2_fnames]
    pdf = make_jb2_pdf(symtbl, jb2_contents)
    safe_rmdir(tmpdir)
    return pdf

