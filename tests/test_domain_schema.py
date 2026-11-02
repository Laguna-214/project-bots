"""Opt-in libvirt Relax NG validation; no libvirt daemon or VM mutations.

Set PROJECT_BOTS_DOMAIN_RNG to an administrator-supplied domain.rng with its
sibling schemas (e.g. libvirt v10.0.0). Uses the installed libxml2, not lxml.
"""
import ctypes
import ctypes.util
import os
from pathlib import Path
import unittest


@unittest.skipUnless(os.environ.get('PROJECT_BOTS_DOMAIN_RNG'), 'optional libvirt schema path not supplied')
class DomainSchemaTests(unittest.TestCase):
    def test_generated_domain_validates_against_libvirt_schema(self):
        from project_bots.compute import ComputeService
        backend = object.__new__(ComputeService)
        backend.root = Path('/home/project-bots/private')
        backend.owner = '11111111-1111-4111-8111-111111111111'
        xml = backend.xml({'id': '22222222-2222-4222-8222-222222222222', 'cpus': 2, 'ram_mib': 4096, 'ssh_port': 22000}).encode()
        lib = ctypes.CDLL(ctypes.util.find_library('xml2'))
        def bind(name, restype, *argtypes):
            fn = getattr(lib, name); fn.restype = restype; fn.argtypes = list(argtypes); return fn
        ptr = ctypes.c_void_p; integer = ctypes.c_int; string = ctypes.c_char_p
        new_parser = bind('xmlRelaxNGNewParserCtxt', ptr, string)
        parse = bind('xmlRelaxNGParse', ptr, ptr)
        new_valid = bind('xmlRelaxNGNewValidCtxt', ptr, ptr)
        read_xml = bind('xmlReadMemory', ptr, string, integer, string, string, integer)
        validate = bind('xmlRelaxNGValidateDoc', integer, ptr, ptr)
        parser = new_parser(os.fsencode(os.environ['PROJECT_BOTS_DOMAIN_RNG']))
        self.assertTrue(parser)
        schema = parse(parser); self.assertTrue(schema)
        valid = new_valid(schema); self.assertTrue(valid)
        doc = read_xml(xml, len(xml), b'domain.xml', None, 0); self.assertTrue(doc)
        try:
            self.assertEqual(validate(valid, doc), 0, 'Generated domain does not match libvirt schema')
        finally:
            for name, obj in [('xmlFreeDoc', doc), ('xmlRelaxNGFreeValidCtxt', valid), ('xmlRelaxNGFree', schema), ('xmlRelaxNGFreeParserCtxt', parser)]:
                bind(name, None, ptr)(obj)
