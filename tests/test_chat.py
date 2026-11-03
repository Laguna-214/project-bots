"""Local SQLite/HTTP contracts, NOT hostile-VM containment acceptance."""
import concurrent.futures
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from project_bots.chat import ChatService
from project_bots.repository import SQLiteRepository
from project_bots.service import PlatformService


class ChatPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'private/state.db'
        self.repo = SQLiteRepository(self.path)
        self.platform = PlatformService(self.repo)
        self.agent = self.platform.create_agent({'name': 'A', 'role': 'r'})
        self.chat = ChatService(self.repo)
        self.group = self.chat.create({'title': 'Group', 'kind': 'group', 'agent_ids': [self.agent['id']]})

    def test_custom_inference_admin_reference_cannot_be_chat_authority(self):
        import os
        from unittest.mock import patch
        from project_bots.service import ConflictError
        secret = 'fixture-inference-' + '0123456789abcdef' * 3
        with patch.dict(os.environ, {'PROJECT_BOTS_LLAMA_TOKEN_ENV': 'CUSTOM_INFERENCE_ADMIN', 'CUSTOM_INFERENCE_ADMIN': secret, 'ALIASED_CHAT': secret}):
            for reference in ('CUSTOM_INFERENCE_ADMIN', 'ALIASED_CHAT'):
                with self.assertRaises(ConflictError):
                    self.chat.configure_identity(self.agent['id'], {'credential_env': reference, 'enabled': True})

    def test_v3_migration_retains_registry_jobs_worker_and_uncertain_admission(self):
        job = self.platform.create_job({'title': 'Keep', 'input': 'Existing', 'agent_id': self.agent['id']})
        worker = self.repo.save_worker({'agent_id': self.agent['id'], 'vm_id': str(uuid.uuid4()), 'credential_env': 'TEST_GATEWAY_ONLY', 'profile': {}})
        self.repo.admission_enqueue('held', 8192, 10, 9999999999, 4)
        self.repo.admission_release('held', uncertain=True)
        with self.repo.transaction() as db:
            for table in ('integration_operations', 'integration_approvals', 'integration_principals', 'chat_messages', 'chat_members', 'chats', 'chat_identities', 'security_events'):
                db.execute('DROP TABLE ' + table)
            db.execute('PRAGMA user_version=3')
        migrated = SQLiteRepository(self.path)
        self.assertEqual(migrated.list('agents'), [self.agent])
        self.assertEqual(migrated.get_job(job['id']), job)
        self.assertEqual(migrated.list('workers'), [worker])
        with migrated.transaction() as db:
            self.assertEqual(db.execute('SELECT state FROM inference_admission').fetchone()[0], 'uncertain')
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 6)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
        self.assertEqual(ChatService(migrated).list(), [])

    def test_concurrent_same_message_id_is_committed_once(self):
        payload = {'client_id': str(uuid.uuid4()), 'content': 'One message'}
        def send(_):
            return ChatService(SQLiteRepository(self.path)).send(self.group['id'], payload)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            rows = list(pool.map(send, range(8)))
        self.assertTrue(all(row == rows[0] for row in rows))
        self.assertEqual(self.chat.history(self.group['id'])['messages'], [rows[0]])

    def test_history_cursor_has_no_cross_chat_leak_and_exposes_next_page(self):
        for i in range(101):
            self.chat.send(self.group['id'], {'client_id': str(uuid.uuid4()), 'content': str(i)})
        other = self.chat.create({'title': 'Other', 'kind': 'individual', 'agent_ids': [self.agent['id']]})
        self.chat.send(other['id'], {'client_id': str(uuid.uuid4()), 'content': 'Other private chat'})
        first = self.chat.history(self.group['id'])
        second = self.chat.history(self.group['id'], first['next_after'])
        self.assertEqual(len(first['messages']), 100)
        self.assertTrue(first['has_more'])
        self.assertEqual([m['content'] for m in second['messages']], ['100'])
        self.assertFalse(second['has_more'])
        self.assertNotIn('Other private chat', str(first) + str(second))

    def test_revoked_actor_is_rechecked_in_transaction_and_denial_persists(self):
        aid = self.agent['id']
        self.chat.configure_identity(aid, {'credential_env': 'TEST_CHAT_ONLY', 'enabled': True})
        self.chat.send(self.group['id'], {'client_id': str(uuid.uuid4()), 'content': 'Allowed'}, aid)
        self.chat.configure_identity(aid, {'credential_env': 'TEST_CHAT_ONLY', 'enabled': False})
        with self.assertRaises(PermissionError):
            self.chat.send(self.group['id'], {'client_id': str(uuid.uuid4()), 'content': 'After revocation'}, aid)
        fresh = ChatService(SQLiteRepository(self.path))
        self.assertEqual(len(fresh.history(self.group['id'])['messages']), 1)
        self.assertEqual(fresh.events()['events'][0]['behavior'], 'message_access_denied')

    def test_unknown_member_rolls_back_membership_update(self):
        with self.assertRaises(ValueError):
            self.chat.set_members(self.group['id'], {'agent_ids': [str(uuid.uuid4())]})
        self.assertEqual(self.chat.list()[0]['agent_ids'], [self.agent['id']])
        self.assertEqual(self.chat.events()['events'], [])
