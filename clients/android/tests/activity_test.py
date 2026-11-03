#!/usr/bin/env python3
"""Execute production MainActivity on JVM with minimal UI/API boundary doubles.
Not Android runtime or adapter/network proof; transport/platform suites cover those.
"""
import os, pathlib, subprocess, tempfile, unittest
ROOT=pathlib.Path(__file__).resolve().parents[3]
TOOLS=pathlib.Path(os.environ['NATIVE_TOOLS_CACHE'])

class ActivityAvailability(unittest.TestCase):
 def test_stop_controls_survive_independent_section_failures(self):
  sources={}
  def add(name,body):
   pkg,cls=name.rsplit('.',1);sources[name.replace('.','/')+'.java']='package '+pkg+'; '+body
  add('android.view.View','public class View { public static final int IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS=8,VISIBLE=0,GONE=8; public interface OnClickListener{void onClick(View v);} public OnClickListener listener; public void setOnClickListener(OnClickListener l){listener=l;} public void setSaveEnabled(boolean b){} public void setImportantForAutofill(int i){} public void setFilterTouchesWhenObscured(boolean b){} public void setEnabled(boolean b){} public void setVisibility(int i){} public void setTag(Object o){tag=o;} Object tag; public Object getTag(){return tag;} }')
  add('android.widget.LinearLayout','public class LinearLayout extends android.view.View { public static final int VERTICAL=1; public java.util.List<android.view.View> children=new java.util.ArrayList<>(); public LinearLayout(Object c){} public void setOrientation(int i){} public void setPadding(int a,int b,int c,int d){} public void addView(android.view.View v){children.add(v);} public void addView(android.view.View v,LayoutParams p){addView(v);} public static class LayoutParams{public LayoutParams(int a,int b,int c){}} }')
  add('android.widget.TextView','public class TextView extends android.view.View { public String value=""; public TextView(Object c){} public void setText(CharSequence s){value=s.toString();} public CharSequence getText(){return value;} public void setTextSize(int i){} public void setTextIsSelectable(boolean b){} public void setAutoLinkMask(int i){} }')
  add('android.widget.Button','public class Button extends TextView { public Button(Object c){super(c);} }')
  add('android.widget.EditText','public class EditText extends TextView { public EditText(Object c){super(c);} public void setHint(String s){} public void setContentDescription(String s){} public void setSingleLine(boolean b){} public void setInputType(int i){} public void setMinLines(int i){} public void addTextChangedListener(android.text.TextWatcher t){} }')
  add('android.widget.CheckBox','public class CheckBox extends Button { boolean checked; public CheckBox(Object c){super(c);} public void setChecked(boolean b){checked=b;} public boolean isChecked(){return checked;} }')
  add('android.widget.ScrollView','public class ScrollView extends LinearLayout { public ScrollView(Object c){super(c);} }')
  add('android.widget.Spinner','public class Spinner extends android.view.View { public Spinner(Object c){} public void setAdapter(Object o){} public Object getSelectedItem(){return "individual";} }')
  add('android.widget.ArrayAdapter','public class ArrayAdapter<T>{public ArrayAdapter(Object c,int i,T[] a){} }')
  add('android.R','public class R { public static class layout {public static int simple_spinner_dropdown_item=1;} }')
  add('android.view.WindowManager','public class WindowManager {public static class LayoutParams{public static int FLAG_SECURE=1;} public void setFlags(int a,int b){} public void addFlags(int a){} }')
  add('android.app.Activity','public class Activity {public static int MODE_PRIVATE=0; public void onCreate(android.os.Bundle b){} protected void onDestroy(){} public void onBackPressed(){} public android.view.WindowManager getWindow(){return new android.view.WindowManager();} public boolean isDeviceProtectedStorage(){return false;} public <T> T getSystemService(Class<T> c){return null;} public java.io.File getDataDir(){return null;} public void setContentView(android.view.View v){} public void runOnUiThread(Runnable r){r.run();} public Pref getPreferences(int i){return new Pref();} public static class Pref {public String getString(String a,String b){return b;} public Pref edit(){return this;} public Pref putString(String a,String b){return this;} public void apply(){}} }')
  add('android.app.AlertDialog','public class AlertDialog { public static Runnable confirmed; public android.view.WindowManager getWindow(){return new android.view.WindowManager();} public interface Click {void click(Object d,int w);} public static class Builder {public Builder(Object o){} public Builder setTitle(String s){return this;} public Builder setMessage(String s){return this;} public Builder setNegativeButton(String s,Click c){return this;} public Builder setPositiveButton(String s,Click c){confirmed=()->c.click(null,0);return this;} public AlertDialog show(){return new AlertDialog();}} }')
  for name,body in {'android.os.Bundle':'','android.os.UserManager':'public boolean isUserUnlocked(){return true;}','android.app.KeyguardManager':'public boolean isDeviceSecure(){return true;}','android.os.storage.StorageManager':'public boolean isEncrypted(java.io.File f){return true;}'}.items():add(name,'public class '+name.rsplit('.',1)[1]+' {'+body+'}')
  add('android.text.InputType','public class InputType{public static int TYPE_CLASS_NUMBER=1,TYPE_NUMBER_VARIATION_PASSWORD=2;}')
  add('android.text.Editable','public interface Editable{}')
  add('android.text.TextWatcher','public interface TextWatcher {void beforeTextChanged(CharSequence s,int a,int b,int c);void onTextChanged(CharSequence s,int a,int b,int c);void afterTextChanged(Editable e);}')
  add('org.json.JSONArray','public class JSONArray {java.util.List<Object> a=new java.util.ArrayList<>(); public int length(){return a.size();} public JSONArray put(Object o){a.add(o);return this;} public JSONObject getJSONObject(int i){return (JSONObject)a.get(i);} public String getString(int i){return a.get(i).toString();} public String toString(int i){return "[]";} }')
  add('org.json.JSONObject','public class JSONObject {java.util.Map<String,Object> m=new java.util.HashMap<>(); public JSONObject put(String k,Object v){m.put(k,v);return this;} public JSONArray optJSONArray(String k){return (JSONArray)m.get(k);} public JSONArray getJSONArray(String k){return (JSONArray)m.get(k);} public String getString(String k){return m.get(k).toString();} public String optString(String k){return m.getOrDefault(k,"").toString();} public boolean optBoolean(String k){return Boolean.TRUE.equals(m.get(k));} public boolean getBoolean(String k){return optBoolean(k);} public long getLong(String k){return 0;} public String toString(int i){return "{}";} }')
  add('app.projectbots.BackendApi','''import org.json.*; public class BackendApi {
   static String fail=""; static volatile int stopped=0; static volatile java.util.concurrent.CountDownLatch stopReply; static java.util.List<String> reads=new java.util.concurrent.CopyOnWriteArrayList<>();
   BackendApi(String s){} void pair(String s){} JSONArray agents(){return new JSONArray();} JSONArray chats(){return new JSONArray();}
   JSONArray jobs()throws Exception{read("jobs");return new JSONArray();}
   JSONObject security()throws Exception{read("security");return new JSONObject().put("agents",new JSONArray().put(new JSONObject().put("agent_id","agent-fixture")));}
   JSONObject events()throws Exception{read("events");return new JSONObject();}
   JSONObject approvals()throws Exception{read("approvals");return new JSONObject().put("approvals",new JSONArray());}
   static void read(String s)throws Exception{reads.add(s);if(fail.contains(s))throw new java.io.IOException("oversize/unavailable");}
   JSONObject stopAll()throws Exception{stopped++;if(stopReply!=null)stopReply.await();return new JSONObject();} JSONObject stopAgent(String s){return new JSONObject();}
   JSONObject createAgent(String a,String b,String c){return new JSONObject();} JSONObject createChat(String a,String b,JSONArray c){return new JSONObject();}
   JSONObject members(String s,JSONArray a){return new JSONObject();} JSONObject history(String s,long l){return new JSONObject();} JSONObject send(String a,String b,String c){return new JSONObject();} JSONObject decide(String s,boolean b){return new JSONObject();}
  }''')
  add('app.projectbots.ActivityAvailabilityTest','''import java.lang.reflect.*; import java.util.*; import java.util.concurrent.*; import android.widget.*; import android.view.View;
  public class ActivityAvailabilityTest {
   static Field field(String s)throws Exception{Field f=MainActivity.class.getDeclaredField(s);f.setAccessible(true);return f;}
   static boolean busy(MainActivity a)throws Exception{for(Field f:MainActivity.class.getDeclaredFields())if(f.getType()==ThreadPoolExecutor.class){f.setAccessible(true);ThreadPoolExecutor e=(ThreadPoolExecutor)f.get(a);if(e.getActiveCount()>0||!e.getQueue().isEmpty())return true;}return false;}
   static void invoke(MainActivity a,String name)throws Exception{Method m=MainActivity.class.getDeclaredMethod(name);m.setAccessible(true);m.invoke(a);}
   static List<String> labels(View v){List<String> out=new ArrayList<>();if(v instanceof TextView)out.add(((TextView)v).value);if(v instanceof LinearLayout)for(View c:((LinearLayout)v).children)out.addAll(labels(c));return out;}
   static android.widget.Button find(View v,String label){if(v instanceof Button&&((Button)v).value.equals(label))return (Button)v;if(v instanceof LinearLayout)for(View c:((LinearLayout)v).children){Button b=find(c,label);if(b!=null)return b;}return null;}
   public static void main(String[] args)throws Exception{
    for(String failure:new String[]{"jobs","events","approvals","jobs events approvals","security jobs events approvals"}){
     MainActivity a=new MainActivity();ThreadPoolExecutor worker=(ThreadPoolExecutor)field("worker").get(a);
     CountDownLatch release=new CountDownLatch(1);for(int i=0;i<2;i++)worker.execute(()->{try{release.await();}catch(Exception e){}});
     BackendApi.fail=failure;BackendApi.reads.clear();field("api").set(a,new BackendApi(""));field("screen").set(a,"Activity");
     try{
      invoke(a,"home");View page=(View)field("page").get(a);
      if(!labels(page).contains("Emergency stop ALL"))throw new AssertionError("global stop absent before informational loads: "+failure);
      release.countDown();long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(3);while(busy(a)&&System.nanoTime()<until)Thread.sleep(5);
      if(!labels(page).contains("Emergency stop ALL"))throw new AssertionError("global stop suppressed: "+failure);
      if(!failure.contains("security")&&!labels(page).contains("Stop agent agent-fixture"))throw new AssertionError("security success lost per-agent stop: "+failure);
      for(String section:new String[]{"jobs","events","approvals","security"}){if(!BackendApi.reads.contains(section))throw new AssertionError("load suppressed: "+section);if(failure.contains(section)&&labels(page).stream().noneMatch(x->x.toLowerCase().contains(section)&&x.contains("failed")))throw new AssertionError("missing local error: "+section);}
      Button all=find(page,"Emergency stop ALL");int before=BackendApi.stopped;all.listener.onClick(all);if(BackendApi.stopped!=before)throw new AssertionError("stop bypassed confirmation");
      android.app.AlertDialog.confirmed.run();until=System.nanoTime()+TimeUnit.SECONDS.toNanos(3);while(busy(a)&&System.nanoTime()<until)Thread.sleep(5);
      if(BackendApi.stopped!=before+1)throw new AssertionError("confirmed global stop did not reach adapter exactly once");
      Button current=find((View)field("page").get(a),"Emergency stop ALL");current.listener.onClick(current);
      invoke(a,"setup");android.app.AlertDialog.confirmed.run();if(BackendApi.stopped!=before+1)throw new AssertionError("stale confirmation reached old session");
     }finally{release.countDown();a.onDestroy();worker.awaitTermination(3,TimeUnit.SECONDS);}
    }
    MainActivity saturated=new MainActivity();ThreadPoolExecutor info=(ThreadPoolExecutor)field("worker").get(saturated);
    CountDownLatch blocked=new CountDownLatch(1);BackendApi.stopReply=new CountDownLatch(1);
    try{
     for(int i=0;i<2;i++)info.execute(()->{try{blocked.await();}catch(Exception e){}});
     field("api").set(saturated,new BackendApi(""));field("screen").set(saturated,"Activity");BackendApi.fail="jobs events approvals";
     invoke(saturated,"home");if(info.getQueue().size()!=4)throw new AssertionError("informational lane not saturated");
     Button all=find((View)field("page").get(saturated),"Emergency stop ALL");int before=BackendApi.stopped;
     all.listener.onClick(all);if(BackendApi.stopped!=before)throw new AssertionError("stop bypassed confirmation under saturation");android.app.AlertDialog.confirmed.run();
     long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(1);while(BackendApi.stopped==before&&System.nanoTime()<until)Thread.sleep(5);
     if(BackendApi.stopped!=before+1)throw new AssertionError("confirmed stop could not dispatch while informational lane blocked/full");
     all.listener.onClick(all);android.app.AlertDialog.confirmed.run();
     if(BackendApi.stopped!=before+1||!((TextView)field("status").get(saturated)).value.contains("Client busy"))throw new AssertionError("concurrent stop was queued/retried instead of explicit busy rejection");
     if(!((ThreadPoolExecutor)field("stopWorker").get(saturated)).getQueue().isEmpty())throw new AssertionError("control mutation queued");
     invoke(saturated,"setup");
    }finally{saturated.onDestroy();blocked.countDown();BackendApi.stopReply.countDown();BackendApi.stopReply=null;info.awaitTermination(3,TimeUnit.SECONDS);}
    System.out.println("PASS reserved stop dispatch under blocked/full informational lane");
    System.out.println("PASS production MainActivity: synchronous global stop, independent loads/local errors, security-success agent controls, stale confirmation invalidation");
   }
  }''')
  with tempfile.TemporaryDirectory(prefix='native-activity-',dir=os.environ.get('TMPDIR')) as tmp:
   tmp=pathlib.Path(tmp)
   for name,content in sources.items():
    p=tmp/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
   main=ROOT/'clients/android/app/src/main/java/app/projectbots'
   production=[main/(name+'.java') for name in ['MainActivity','SelectionGate','Endpoint','HistoryLedger','DraftRevision']]
   subprocess.run([str(TOOLS/'jdk-17.0.17+10/bin/javac'),'-d',str(tmp),*map(str,tmp.rglob('*.java')),*map(str,production)],check=True,capture_output=True)
   run=subprocess.run([str(TOOLS/'jdk-17.0.17+10/bin/java'),'-cp',str(tmp),'app.projectbots.ActivityAvailabilityTest'],capture_output=True,text=True,timeout=25)
   self.assertEqual(run.returncode,0,run.stdout+run.stderr)
   print(run.stdout.strip())
if __name__=='__main__':unittest.main()
