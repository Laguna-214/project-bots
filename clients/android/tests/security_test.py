#!/usr/bin/env python3
"""Architecture tripwires, not Android runtime acceptance."""
import pathlib, unittest, xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parents[1]
class NativeSecurity(unittest.TestCase):
 def test_no_remote_execution_or_network_channels(self):
  files=list((ROOT/'app/src/main/java').rglob('*.java'))
  source='\n'.join(p.read_text() for p in files)
  for banned in ['android.webkit','WebView','JavascriptInterface','startActivity(', 'loadUrl(', 'Socket(', 'Runtime.getRuntime','ProcessBuilder','setHostnameVerifier','setSSLSocketFactory','SSLContext','TrustManager']:
   self.assertNotIn(banned,source)
  network=[p.name for p in files if '.openConnection(' in p.read_text()]
  self.assertEqual(network,['NativeTransport.java'])
  t=(ROOT/'app/src/main/java/app/projectbots/NativeTransport.java').read_text()
  for required in ['setInstanceFollowRedirects(false)','setFixedLengthStreamingMode','setConnectTimeout','setReadTimeout','MAX_RESPONSE','MAX_REQUEST','status>=300&&status<400']:
   self.assertIn(required,t)
 def test_native_screens_privacy_and_typed_api(self):
  s=(ROOT/'app/src/main/java/app/projectbots/MainActivity.java').read_text()
  for required in ['"Chats"','"Agents"','"Activity"','isEncrypted(getDataDir())','isDeviceSecure()','isUserUnlocked()','FLAG_SECURE','SelectionGate','setSaveEnabled(false)','setImportantForAutofill','setFilterTouchesWhenObscured(true)']:
   self.assertIn(required,s)
  self.assertNotIn('.request(',s)
  self.assertNotIn('putString("token"',s)
 def test_manifest_least_privilege(self):
  r=ET.parse(ROOT/'app/src/main/AndroidManifest.xml').getroot();a='{http://schemas.android.com/apk/res/android}'
  self.assertEqual([e.get(a+'name') for e in r.findall('uses-permission')],['android.permission.INTERNET'])
  app=r.find('application');self.assertEqual(app.get(a+'allowBackup'),'false');self.assertNotEqual(app.get(a+'debuggable'),'true');self.assertIn('debuggable false',(ROOT/'app/build.gradle').read_text())
if __name__=='__main__':unittest.main()
