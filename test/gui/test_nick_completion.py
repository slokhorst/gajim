import unittest
from unittest.mock import MagicMock

from gajim.common import app

from gajim.gtk.groupchat_nick_completion import GroupChatNickCompletion


class Test(unittest.TestCase):

    def test_generate_suggestions(self):
        participant_names = [
            'aaaa',
            'xaaaz',
            'xxx',
            'xxxxz'
        ]

        participants: list[MagicMock] = []
        for name in participant_names:
            participant = MagicMock()
            participant.name = name
            participants.append(participant)

        app.get_client = MagicMock()

        app.storage.archive = MagicMock()
        app.storage.archive.get_recent_muc_nicks = MagicMock(
            return_value=['fooo'])

        gen = GroupChatNickCompletion()
        contact = MagicMock()
        contact.get_participants = MagicMock(return_value=participants)

        gen.switch_contact(contact)

        r = gen._generate_suggestions(prefix='x')
        self.assertEqual(r, ['xaaaz', 'xxx', 'xxxxz'])

        r = gen._generate_suggestions(prefix='')
        self.assertEqual(r, ['fooo', 'aaaa', 'xaaaz', 'xxx', 'xxxxz'])

        r = gen._generate_suggestions(prefix='m')
        self.assertEqual(r, [])


if __name__ == '__main__':
    unittest.main()
