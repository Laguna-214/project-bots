"""Installed HTTP/restart security checks; isolated, not host containment."""
import unittest
import test_platform


class SecurityHTTPTests(unittest.TestCase):
    setUp = test_platform.InstalledPlatformTests.setUp
    start = test_platform.InstalledPlatformTests.start
    stop = test_platform.InstalledPlatformTests.stop
    request = test_platform.InstalledPlatformTests.request
    pair = test_platform.InstalledPlatformTests.pair

    def test_admin_stop_survives_installed_process_restart_and_read_routes_work(self):
        self.request('GET', '/api/security/status', status=403)
        self.pair()
        a = self.request('POST', '/api/agents', {'name': 'A', 'role': 'r'}, 201)
        j = self.request('POST', '/api/jobs', {'title': 'queued', 'input': 'x', 'agent_id': a['id']}, 201)
        state = self.request('POST', '/api/security/emergency-stop', {'reason': 'installed fixture stop'})
        self.assertTrue(state['global_stop'])
        self.assertFalse(state['protected'])
        incident = state['incidents'][0]
        self.assertEqual(incident['agent_id'], a['id'])
        self.assertEqual(self.request('GET', '/api/jobs/' + j['id'])['status'], 'canceled')
        path = '/api/security/incidents/' + incident['id']
        self.assertEqual(self.request('GET', path)['id'], incident['id'])
        ack = self.request('POST', path + '/acknowledge', {'note': 'reviewed fixture'})
        self.assertEqual(ack['status'], 'acknowledged')
        self.request('POST', '/api/security/recover', {'note': 'global must not clear agent latch'}, 409)
        self.stop(); self.start(); self.pair()
        self.assertTrue(self.request('GET', '/api/security/status')['global_stop'])
        self.request('POST', '/api/jobs', {'title': 'blocked', 'input': 'x'}, 409)
        self.request('POST', '/api/jobs/' + j['id'] + '/claim', {'agent_id': a['id']}, 409)
        self.assertEqual(self.request('GET', '/api/agents')[0]['id'], a['id'])
        self.assertEqual(self.request('GET', path)['status'], 'acknowledged')
        recovered = self.request('POST', path + '/recover', {'note': 'registry-only fixture recovery', 'credential_rotated': True})
        self.assertEqual(recovered['status'], 'recovered')
        self.assertTrue(self.request('GET', '/api/security/status')['global_stop'])
        restored = self.request('POST', '/api/security/recover', {'note': 'separate global recovery'})
        self.assertFalse(restored['global_stop'])
        self.request('POST', '/api/jobs', {'title': 'queue restored', 'input': 'safe fixture queue'}, 201)

    def test_chat_credentials_cannot_report_recover_or_acknowledge_incidents(self):
        self.stop()
        self.env['FIXTURE_CHAT_TOKEN'] = 'scoped-fixture-chat-' + 'a' * 40
        self.start(); self.pair()
        a = self.request('POST', '/api/agents', {'name': 'A', 'role': 'r'}, 201)['id']
        self.request('POST', '/api/agents/' + a + '/chat-identity', {'credential_env': 'FIXTURE_CHAT_TOKEN', 'enabled': True})
        hdr = {'Authorization': 'Bearer ' + self.env['FIXTURE_CHAT_TOKEN'], 'Content-Type': 'application/json'}
        for path, body in [('/api/security/emergency-stop', {'reason': 'escalation'}), ('/api/security/recover', {'note': 'escalation'}), ('/api/security/incidents', {'agent_id': a})]:
            self.request('POST', path, body, 403, headers=hdr)
        self.request('GET', '/api/security/status', status=403, headers=hdr)
        incident = self.request('POST', '/api/security/incidents', {'agent_id': a, 'severity': 'high', 'behavior': 'fixture', 'resource': 'fixture', 'evidence': 'fixture observation'}, 201)
        # Even re-enabling the same old identity cannot overcome containment.
        self.request('POST', '/api/agents/' + a + '/chat-identity', {'credential_env': 'FIXTURE_CHAT_TOKEN', 'enabled': True})
        self.request('GET', '/api/chats', status=403, headers=hdr)
        self.request('POST', '/api/security/incidents/' + incident['id'] + '/acknowledge', {'note': 'escalation'}, 403, headers=hdr)
