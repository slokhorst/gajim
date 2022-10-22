import unittest

from gajim.common.text_helpers import escape_iri_path_segment
from gajim.common.text_helpers import jid_to_iri


class Test(unittest.TestCase):
    def test_escape_iri_path_segment(self):
        self.assertEqual(escape_iri_path_segment(''), '', '<empty string>')

        über = 'u\u0308ber'
        self.assertEqual(escape_iri_path_segment(über), über)

        self.assertEqual(
            escape_iri_path_segment(''.join(chr(c) for c in range(0x20,0x7F))),
            '%20!%22%23$%25&\'()*+,-.%2F0123456789:;%3C=%3E%3F@ABCDEFGHIJKLMN'
            'OPQRSTUVWXYZ%5B%5C%5D%5E_%60abcdefghijklmnopqrstuvwxyz%7B%7C%7D~',
            'ASCII printable')

        self.assertEqual(escape_iri_path_segment(
            ''.join(chr(c) for c in range(0x01,0x20)) + chr(0x7F)),
            ''.join('%%%02X'%c for c in range(0x01,0x20)) + '%7F',
            'ASCII control (no null)')


    def test_jid_to_iri(self):
        jid = r'foo@bar'
        self.assertEqual(jid_to_iri(jid), fr'xmpp:{jid}', jid)
        jid = r'my\20self@[::1]/home'
        self.assertEqual(jid_to_iri(jid),
            r'xmpp:my%5C20self@%5B::1%5D/home', jid)


if __name__ == '__main__':
    unittest.main()
