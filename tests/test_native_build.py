from pathlib import Path
import os,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class NativeBuildCacheTests(unittest.TestCase):
 def test_bootstrap_rejects_unsafe_cache_without_chmod(self):
  with tempfile.TemporaryDirectory() as folder:
   cache=Path(folder)/'unsafe';cache.mkdir(mode=0o755)
   env=dict(os.environ,NATIVE_TOOLS_CACHE=str(cache))
   r=subprocess.run([sys.executable,'-c','import runpy;runpy.run_path('+repr(str(ROOT/'clients/tools/bootstrap.py'))+',run_name="import_only")'],env=env,capture_output=True,text=True)
   self.assertNotEqual(r.returncode,0)
   self.assertEqual(cache.stat().st_mode&0o777,0o755)
 def test_build_tool_defaults_do_not_depend_on_hermes(self):
  for name in ('bootstrap.py','build-android.sh'):
   self.assertNotIn('.hermes/profiles', (ROOT/'clients/tools'/name).read_text())
