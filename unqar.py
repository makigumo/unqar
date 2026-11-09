#!/usr/bin/env python3

import base64
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
        self.file = None
        self.file = open(file_name, 'rb')

    def read(self, size):
        value = self.file.read(size)
        if size != len(value):
            raise BinaryEOFException
        return value

    def unpack(self, type_format):
        type_size = struct.calcsize(type_format)
        return struct.unpack(type_format, self.read(type_size))[0]

    def __del__(self):
        if self.file is not None:
            self.file.close()


# Static Huffman codebook used by version 1 QAR archives.  Each 32-bit
# little-endian value contains (code << 5) | code_length for the byte value
# equal to its index.  This is the ARC_ENCODING_TABLE from the reference
# implementation.
_HUFFMAN_CODEBOOK = base64.b64decode(
    "owAAAGomAAAqEQAArfQDAKoFAADNMQEATVsBAG5HBgDKBQAApgcAAGYEAACQGhkA7TEBACYEAABP"
    "jwwAz9MPAOoFAACORwYAjlIEAFDbCgAtMQEAsI0JAHDbCgCyamQADVsBANCNCQCPbQUAciZFAPCn"
    "HwASJ0UAjJEBALFMPwDEAQAAKmQAAMYEAABIEAAACiYAAI0jAwDnDwAAzukHAOgEAABoBAAAy4oA"
    "AAz6AQCqZAAAhgIAAEpFAACIHwAA5gIAAEYCAAAHAgAAaBkAAGgQAACoCQAAyAkAAGk/AADIBAAA"
    "STwAAKYGAABmAAAApgAAACcPAACGAAAAsB8ZAEomAACGAQAACBAAAGgYAACHAAAAxwkAAGgRAADo"
    "CQAAKTwAAEcCAABORwYA61YAAMcMAADoCgAAhwgAAEgZAAAoEAAA6mQAAEcFAABIGAAAxgIAAGk8"
    "AAAqKwAA64oAAIoFAACKZAAASisAAAcMAAAs+gEA5wkAAFAaGQAFAQAALVsBAMYHAACmAwAAxgYA"
    "AAUAAACFAQAA5wwAAEgBAAAJPAAApgEAAC7pBwBKZAAAhgYAAOYGAADlAQAARQIAAKUAAAAKEQAA"
    "ZQAAAOUAAAClAQAAJgYAAGuKAAAKZAAACkUAAKp+AACpCAAATmMCAIYDAADOYgIAymQAAHKffgAK"
    "KwAADukHAE5SBADQHxkArukHAJDbCgBQigkAcRQTAM5HBgDRNDIAERsTAFPfVgAxlyIA8/zIADIq"
    "JgDyamQArlIEANKZfgBxERMAk9fIABCKCQBSn34AEph+ABMx/QAwGhkA0RQTAHP2yACz0MgAsjcm"
    "AFNcigDxNDIAE//IAA0pAgCwSxEAsZMiAJP/yADRkyIA0TUyAHKYfgBzXIoAsEkRAPG3FQARkyIA"
    "U/bIALIoJgCT0MgA0ikmADP/yADQ2woA09DIABP3yAAz98gA0zP9AFP/yAAz/MgAdHz6AVEREwCz"
    "/8gAc99WANI3JgBSfmQAU/zIAHI2JgDSKiYAbSMDANBLEQBvxAQAMRUTADKffgAz3VYA8mtkAPMz"
    "/QBxTD8Ac/zIADKYfgCz18gAUph+ADPVyABSNiYAMidFAG/FBADT/8gAkUw/APPQyADT/MgAMzH9"
    "AJNMigATPv0AETQyAJPVyABT98gAE1yKAPJuKwCT3VYAEntkABPVyADuYgIA8EsRAJJvKwAzXIoA"
    "s9XIABPdVgDz/8gA8ikmAFEVEwBz98gAs91WAFR8+gFTMf0Ac//IALJuKwCSNyYADmICAJIoJgDy"
    "KiYAE/zIABIqJgBzMf0As0yKAPI3JgDQGhkA8ZMiANFMPwCxPTIAkIgJAPE9MgCNMQEAzlIEAA=="
)


def _build_huffman_tree():
    tree = {}
    for value in range(256):
        packed = struct.unpack_from('<I', _HUFFMAN_CODEBOOK, value * 4)[0]
        code_length = packed & 0x1f
        code = packed >> 5
        node = tree
        for bit_index in range(code_length - 1, -1, -1):
            bit = (code >> bit_index) & 1
            if bit_index == 0:
                node[bit] = value
            else:
                node = node.setdefault(bit, {})
    return tree


_HUFFMAN_TREE = _build_huffman_tree()


def decode_version_1(data, last_byte_flag):
    """Decode the Huffman-compressed payload of a version 1 QAR entry."""
    if not data:
        return b''

    # The final byte is padded in its low bits.  A flag of zero means that
    # all eight bits of the final byte are used.
    skip_bits = last_byte_flag if last_byte_flag <= 7 else 8
    valid_bits = len(data) * 8 - skip_bits

    result = bytearray()
    node = _HUFFMAN_TREE
    for bit_index in range(valid_bits):
        bit = (data[bit_index >> 3] >> (7 - (bit_index & 7))) & 1
        node = node[bit]
        if isinstance(node, int):
            result.append(node)
            node = _HUFFMAN_TREE
    return bytes(result)


def print_usage():
    print("Usage: %s [-l] <qar file> [<output path>]" % sys.argv[0])
    print("-l     list files in qar file")


def main():
    list_files = False
    args = sys.argv[1:]

    if args and args[0] == '-l':
        list_files = True
        args = args[1:]

    if not args:
        print_usage()
        return 1

    qar_path = args[0]
    output_path = pathlib.Path.cwd()
    if not list_files and len(args) > 1:
        output_path = pathlib.Path(args[1])

    try:
        binary_reader = BinaryReader(qar_path)
    except OSError:
        print("Error: File not found: %s" % qar_path)
        print_usage()
        return 1

    try:
        magic = binary_reader.unpack('<B')
        version = binary_reader.unpack('<B')

        if magic == 0x71:
            endian = '<'
        elif magic == 0x75:
            endian = '>'
        else:
            print("Not a supported qar file.")
            print_usage()
            return 2

        if version == 0 or version > 2:
            print("Unsupported qar version %d." % version)
            return 2

        file_count = binary_reader.unpack(endian + 'H')
        print("Going to extract %d files." % file_count)

        for _ in range(file_count):
            data_len = binary_reader.unpack(endian + 'I')
            flag = binary_reader.unpack('<B')
            binary_reader.unpack('<B')  # reserved
            name_len = binary_reader.unpack(endian + 'H')
            name = os.fsdecode(binary_reader.read(name_len))
            data = binary_reader.read(data_len)

            if data_len == 0:
                extracted = b''
            elif version == 1:
                extracted = decode_version_1(data, flag)
            else:
                extracted = zlib.decompress(data)

            if list_files:
                print("%s" % name)
            else:
                p = output_path.joinpath(name)
                p.parent.mkdir(parents=True, exist_ok=True)
                with p.open('wb') as fh:
                    fh.write(extracted)
                print("extracted file: %s" % p)

    except BinaryEOFException:
        print("Error: Possibly corrupted file.")
        return 1
    except zlib.error as e:
        print("Error: Failed to decompress qar file: %s" % e)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
