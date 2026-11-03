"""Actual libxml2 RelaxNG validation, optional trusted schema; no VM execution."""
import ctypes
import ctypes.util
import os
import unittest
from project_bots.protected_compute import Binding, domain_xml


@unittest.skipUnless(os.environ.get('PROJECT_BOTS_DOMAIN_RNG'), 'optional libvirt schema path not supplied')
class ProtectedSchemaTests(unittest.TestCase):
    def test_fixed_protected_domain_validates(self):
        b = Binding.parse(dict(vm_id='a3ec8c2c-a7a0-4164-a357-f006175d189e',
                               owner='fd698b30-a01a-4ebc-a4bc-a8ddc01bf9c6', uid=62001, gid=62001,
                               broker_ipv4='192.0.2.10', broker_port=21435))
        lib = ctypes.CDLL(ctypes.util.find_library('xml2'))
        ptr = ctypes.c_void_p
        def bind(name, result, *args):
            function = getattr(lib, name)
            function.restype = result; function.argtypes = list(args)
            return function
        parser = bind('xmlRelaxNGNewParserCtxt', ptr, ctypes.c_char_p)(os.fsencode(os.environ['PROJECT_BOTS_DOMAIN_RNG']))
        self.assertTrue(parser)
        schema = bind('xmlRelaxNGParse', ptr, ptr)(parser)
        self.assertTrue(schema)
        validator = bind('xmlRelaxNGNewValidCtxt', ptr, ptr)(schema)
        self.assertTrue(validator)
        try:
            for software in (False, True):
                xml = domain_xml(b, software_emulation=software).encode()
                doc = bind('xmlReadMemory', ptr, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int)(xml, len(xml), b'protected.xml', None, 0)
                self.assertTrue(doc)
                try:
                    self.assertEqual(bind('xmlRelaxNGValidateDoc', ctypes.c_int, ptr, ptr)(validator, doc), 0)
                finally:
                    bind('xmlFreeDoc', None, ptr)(doc)
        finally:
            for name, obj in [('xmlRelaxNGFreeValidCtxt', validator), ('xmlRelaxNGFree', schema), ('xmlRelaxNGFreeParserCtxt', parser)]:
                bind(name, None, ptr)(obj)
