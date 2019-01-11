#!/usr/bin/env python3

import os
import pathlib
import struct
import sys
import zlib


class BinaryEOFException(Exception):
    def __init__(self):
        pass

    def __str__(self):
        return 'Premature end of file.'


class BinaryReader:

    def __init__(self, file_name):
        self.file = open(file_name, 'rb')

    def unpack(self, type_format):
        type_size = struct.calcsize(type_format)
        value = self.file.read(type_size)
        if type_size != len(value):
            raise BinaryEOFException
        return struct.unpack(type_format, value)[0]

    def __del__(self):
        self.file.close()


if len(sys.argv) < 2:
    print("Usage: %s <qar file> [<output path>]" % sys.argv[0])
    exit(1)

binaryReader = BinaryReader(sys.argv[1])
output_path = ""
if len(sys.argv) > 2:
    output_path = str(sys.argv[2])

try:
    magic = binaryReader.unpack('<H')  # 71 02
    if magic != 0x0271:
        print("Not a supported qar file.")
        print("Usage: %s <qar file>" % sys.argv[0])
        exit(2)
    file_count = binaryReader.unpack('<H')
    print("Going to extract %d files." % file_count)
    for i in range(0, file_count):
        data_len = binaryReader.unpack('<I')
        unknown2 = binaryReader.unpack('<H')  # 00 07 or 00 7f
        name_len = binaryReader.unpack('<H')
        name = binaryReader.unpack('<%ds' % name_len).decode('utf-8')
        data = binaryReader.unpack('<%ds' % data_len)
        extracted = zlib.decompress(data)
        p = pathlib.Path(output_path).joinpath(name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with p.open('wb') as fh:
            fh.write(extracted)
        print("extracted file: %s" % p)


except BinaryEOFException:
    print("Error: Possibly corrupted file.")
