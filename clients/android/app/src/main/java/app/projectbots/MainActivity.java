package app.projectbots;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.KeyguardManager;
import android.os.Bundle;
import android.os.UserManager;
import android.os.storage.StorageManager;
import android.text.InputType;
import android.view.View;
import android.view.WindowManager;
import android.widget.*;
import org.json.*;
import java.util.*;
import java.util.concurrent.*;

/** Native plaintext presentation. No remote document, resource, URL or code execution. */
public final class MainActivity extends Activity {
 private final SelectionGate gate=new SelectionGate();
 private final ThreadPoolExecutor worker=new ThreadPoolExecutor(2,2,0,TimeUnit.SECONDS,new ArrayBlockingQueue<>(4));
 // No informational work or queued mutations may occupy the emergency control lane.
 private final ThreadPoolExecutor stopWorker=new ThreadPoolExecutor(1,1,0,TimeUnit.SECONDS,new SynchronousQueue<>());
 private BackendApi api;
 private LinearLayout page;
 private TextView status;
 private String screen="Chats",selectedId="",pendingContent="",pendingId="";
 private HistoryLedger history=new HistoryLedger();
 private DraftRevision draftRevision=new DraftRevision();
 private LinearLayout historyBox;
 private EditText draft;
 private JSONArray agents=new JSONArray();
 interface Work<T>{T run()throws Exception;}
 interface Done<T>{void accept(T result)throws Exception;}
 @Override public void onCreate(Bundle state){
  super.onCreate(state);getWindow().setFlags(WindowManager.LayoutParams.FLAG_SECURE,WindowManager.LayoutParams.FLAG_SECURE);
  if(isDeviceProtectedStorage()||!getSystemService(UserManager.class).isUserUnlocked()||!getSystemService(KeyguardManager.class).isDeviceSecure()||!getSystemService(StorageManager.class).isEncrypted(getDataDir())){
   TextView denied=new TextView(this);denied.setText("Project Bots requires unlocked, OS-encrypted credential storage and a secure screen lock. No backend contacted.");setContentView(denied);return;
  }
  setup();
 }
 private LinearLayout column(){LinearLayout box=new LinearLayout(this);box.setOrientation(LinearLayout.VERTICAL);return box;}
 private void protect(View v){v.setSaveEnabled(false);v.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);v.setFilterTouchesWhenObscured(true);}
 private void layout(String heading,boolean navigation){
  gate.advance();LinearLayout root=column();root.setPadding(20,16,20,16);protect(root);
  TextView title=new TextView(this);title.setText(heading);title.setTextSize(22);root.addView(title);
  if(navigation){
   LinearLayout nav=new LinearLayout(this);
   for(String name:new String[]{"Chats","Agents","Activity"})button(nav,name,()->{selectedId="";screen=name;home();});root.addView(nav);
   button(root,"Change endpoint / forget session",this::setup);
  }
  status=new TextView(this);status.setText("Only explicit API actions; no offline queue. Stop outcomes require independent verification.");root.addView(status);
  ScrollView scroll=new ScrollView(this);page=column();protect(page);scroll.addView(page);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);
 }
 private TextView text(LinearLayout box,String value){TextView t=new TextView(this);t.setText(value);t.setTextIsSelectable(true);t.setAutoLinkMask(0);protect(t);box.addView(t);return t;}
 private EditText input(LinearLayout box,String label){EditText e=new EditText(this);e.setHint(label);e.setContentDescription(label);protect(e);box.addView(e);return e;}
 private Button button(LinearLayout box,String label,Runnable action){Button b=new Button(this);b.setText(label);protect(b);box.addView(b);b.setOnClickListener(v->action.run());return b;}
 private <T> void run(Button button,Work<T> work,Done<T> done){
  runCaptured(button,work,done,gate.capture());
 }
 private long gateSnapshot(){return gate.capture();}
 private <T> void runCaptured(Button button,Work<T> work,Done<T> done,long generation){
  runCaptured(button,work,done,generation,null);
 }
 private <T> void runStop(Button button,Work<T> work,Done<T> done){
  runCaptured(button,work,done,gate.capture(),null,stopWorker);
 }
 private <T> void runCaptured(Button button,Work<T> work,Done<T> done,long generation,Runnable failed){
  runCaptured(button,work,done,generation,failed,worker);
 }
 private <T> void runCaptured(Button button,Work<T> work,Done<T> done,long generation,Runnable failed,ThreadPoolExecutor executor){
  if(button!=null)button.setEnabled(false);
  status.setText("Contacting selected backend…");
  try{executor.execute(()->{
   try{
    if(!gate.current(generation))return;
    T result=work.run();runOnUiThread(()->{
     if(!gate.current(generation))return;
     try{if(button!=null)button.setEnabled(true);status.setText("Backend response received. Registration/control-plane status is not runtime enforcement proof.");done.accept(result);}
     catch(Exception e){if(failed!=null)failed.run();else status.setText("Invalid backend response; refresh required.");}
    });
   }catch(Exception e){runOnUiThread(()->{if(gate.current(generation)){if(button!=null)button.setEnabled(true);if(failed!=null){failed.run();return;}status.setText("Request failed ("+e.getClass().getSimpleName()+"). Mutation outcome may be uncertain; no automatic retry. Check backend/certificate/connectivity, then refresh.");}});}
  });}catch(RejectedExecutionException e){if(button!=null)button.setEnabled(true);if(failed!=null){failed.run();return;}status.setText("Client busy; action was not queued. Retry after current requests finish.");}
 }
 private void setup(){
  api=null;agents=new JSONArray();selectedId="";pendingId="";pendingContent="";draft=null;historyBox=null;history=new HistoryLedger();
  layout("Project Bots — pair native client",false);
  text(page,"HTTPS origin only outside exact loopback. Certificates must be system-trusted. Sessions stay only in memory; changing endpoint/closing requires a fresh console pairing code. Pending mutations may already have reached the old backend.");
  EditText endpoint=input(page,"Backend origin");endpoint.setSingleLine(true);endpoint.setText(getPreferences(MODE_PRIVATE).getString("endpoint","https://"));
  EditText code=input(page,"Eight-digit console pairing code");code.setSingleLine(true);code.setInputType(InputType.TYPE_CLASS_NUMBER|InputType.TYPE_NUMBER_VARIATION_PASSWORD);
  Button pair=button(page,"Pair",()->{});
  pair.setOnClickListener(v->{String origin=Endpoint.parse(endpoint.getText().toString());String entered=code.getText().toString();
   if(origin==null||!entered.matches("[0-9]{8}")){status.setText("Enter an HTTPS origin and exact eight-digit pairing code.");return;}
   BackendApi next=new BackendApi(origin);code.setText("");getPreferences(MODE_PRIVATE).edit().putString("endpoint",origin).apply();
   run(pair,()->{next.pair(entered);return next;},result->{api=result;screen="Chats";home();});
  });
 }
 private void home(){
  if(api==null){setup();return;}BackendApi client=api;layout(screen,true);
  if(screen.equals("Chats"))run(null,()->new JSONArray[]{client.agents(),client.chats()},result->{agents=result[0];renderChats(result[1]);});
  else if(screen.equals("Agents"))run(null,client::agents,result->{agents=result;renderAgents();});
  else renderActivity();
 }
 private void renderChats(JSONArray chats)throws Exception{
  button(page,"Refresh chats",this::home);
  if(chats.length()==0)text(page,"No chats recorded.");
  for(int i=0;i<chats.length();i++){JSONObject chat=chats.getJSONObject(i);button(page,chat.getString("title")+" · "+chat.getString("kind"),()->openChat(chat));}
  text(page,"Create chat");EditText title=input(page,"Chat title");
  Spinner kind=new Spinner(this);kind.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"individual","group"}));page.addView(kind);
  LinearLayout memberBox=column();page.addView(memberBox);List<CheckBox> choices=memberChoices(memberBox,new JSONArray());
  Button create=button(page,"Create chat",()->{});BackendApi client=api;
  create.setOnClickListener(v->{String name=title.getText().toString(),type=kind.getSelectedItem().toString();JSONArray members=chosen(choices);run(create,()->client.createChat(name,type,members),this::openChat);});
 }
 private List<CheckBox> memberChoices(LinearLayout box,JSONArray selected)throws Exception{
  Set<String> ids=new HashSet<>();for(int i=0;i<selected.length();i++)ids.add(selected.getString(i));List<CheckBox> choices=new ArrayList<>();
  for(int i=0;i<agents.length();i++){JSONObject agent=agents.getJSONObject(i);CheckBox b=new CheckBox(this);b.setText(agent.getString("name"));b.setTag(agent.getString("id"));b.setChecked(ids.contains(agent.getString("id")));protect(b);box.addView(b);choices.add(b);}return choices;
 }
 private JSONArray chosen(List<CheckBox> choices){JSONArray out=new JSONArray();for(CheckBox b:choices)if(b.isChecked())out.put(b.getTag().toString());return out;}
 private void openChat(JSONObject chat){
  try{
   selectedId=chat.getString("id");pendingContent="";pendingId="";history=new HistoryLedger();draftRevision=new DraftRevision();layout(chat.getString("title"),true);BackendApi client=api;String id=selectedId;
   button(page,"Back to chats",()->{screen="Chats";home();});button(page,"Refresh history",()->openChat(chat));
   historyBox=column();page.addView(historyBox);draft=input(page,"Message (plain text)");draft.setMinLines(2);
   draft.addTextChangedListener(new android.text.TextWatcher(){public void beforeTextChanged(CharSequence s,int start,int count,int after){} public void onTextChanged(CharSequence s,int start,int before,int count){draftRevision.edited();}public void afterTextChanged(android.text.Editable s){}});
   Button send=button(page,"Send persistent message",()->{});
   send.setOnClickListener(v->{String content=draft.getText().toString();if(content.isEmpty()){status.setText("Enter a message.");return;}
    if(!content.equals(pendingContent)||pendingId.isEmpty()){pendingContent=content;pendingId=UUID.randomUUID().toString();}String operation=pendingId;long sentRevision=draftRevision.capture();
    run(send,()->client.send(id,operation,content),result->{if(draftRevision.unchanged(sentRevision))draft.setText("");pendingId="";pendingContent="";loadHistory(null,client,id);});
   });
   Button more=button(page,"Load next messages",()->{});more.setOnClickListener(v->loadHistory(more,client,id));
   text(page,"Membership — server enforces per-identity access. Individual chats require exactly one agent.");
   List<CheckBox> choices=memberChoices(page,chat.getJSONArray("agent_ids"));Button save=button(page,"Save membership",()->{});
   save.setOnClickListener(v->{JSONArray members=chosen(choices);run(save,()->client.members(id,members),this::openChat);});
   loadHistory(more,client,id);
  }catch(Exception e){status.setText("Invalid chat response.");}
 }
 private void loadHistory(Button more,BackendApi client,String id){
  long after=history.cursor();run(more,()->client.history(id,after),result->{
   JSONArray messages=result.getJSONArray("messages");for(int i=0;i<messages.length();i++){JSONObject m=messages.getJSONObject(i);long sequence=m.getLong("sequence");if(history.first(sequence))text(historyBox,m.getString("sender")+" · "+m.getString("created_at")+"\n"+m.getString("content"));}
   history.advance(result.getLong("next_after"));if(more!=null)more.setVisibility(result.getBoolean("has_more")?View.VISIBLE:View.GONE);
  });
 }
 private void renderAgents()throws Exception{
  button(page,"Refresh agents",this::home);text(page,"Agent definitions only; creation does not enroll a conversational runner or launch a worker. Model is an existing backend model name, not a remote URL.");
  for(int i=0;i<agents.length();i++)text(page,agents.getJSONObject(i).toString(2));
  EditText name=input(page,"Agent name"),role=input(page,"Role"),model=input(page,"Model name (optional)");Button create=button(page,"Create agent definition",()->{});BackendApi client=api;
  create.setOnClickListener(v->{String n=name.getText().toString(),r=role.getText().toString(),m=model.getText().toString();run(create,()->client.createAgent(n,r,m),result->home());});
 }
 private void confirm(String title,String detail,Runnable action){long generation=gateSnapshot();new AlertDialog.Builder(this).setTitle(title).setMessage(detail).setNegativeButton("Cancel",null).setPositiveButton("Confirm",(d,w)->{if(gate.current(generation))action.run();}).show().getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);}
 private <T> void loadSection(String name,LinearLayout box,Work<T> work,Done<T> done){
  runCaptured(null,work,done,gate.capture(),()->text(box,name+" failed; refresh required. Global stop remains available; no automatic retry."));
 }
 private void renderActivity(){
  BackendApi client=api;button(page,"Refresh activity/security",this::home);
  // Render the confirmed global action before scheduling any informational request.
  Button all=button(page,"Emergency stop ALL",()->{});all.setOnClickListener(v->confirm("Stop all agents?","Requests the global control-plane stop. Runtime/network outcomes must be independently verified; no automatic recovery.",()->runStop(all,client::stopAll,reply->home())));
  LinearLayout securityBox=column(),jobsBox=column(),eventsBox=column(),approvalsBox=column();
  for(LinearLayout box:new LinearLayout[]{securityBox,jobsBox,eventsBox,approvalsBox})page.addView(box);
  text(securityBox,"Security observations and incident evidence (not proof of isolation)");
  text(jobsBox,"Jobs / reported activity");text(eventsBox,"Chat security events");
  text(approvalsBox,"Human approvals — untrusted proposed payloads are plain text, never commands");
  loadSection("Security",securityBox,client::security,security->{
   JSONArray states=security.optJSONArray("agents");if(states!=null)for(int i=0;i<states.length();i++){String id=states.getJSONObject(i).getString("agent_id");Button stop=button(securityBox,"Stop agent "+id,()->{});stop.setOnClickListener(v->confirm("Stop agent?",id+"\nRecords a high-severity incident and containment attempt. Review partial outcomes.",()->runStop(stop,()->client.stopAgent(id),reply->home())));}
   text(securityBox,security.toString(2));
  });
  loadSection("Jobs",jobsBox,client::jobs,jobs->text(jobsBox,jobs.toString(2)));
  loadSection("Events",eventsBox,client::events,events->text(eventsBox,events.toString(2)));
  loadSection("Approvals",approvalsBox,client::approvals,result->{
   JSONArray proposals=result.getJSONArray("approvals");
   for(int i=0;i<proposals.length();i++){JSONObject p=proposals.getJSONObject(i);text(approvalsBox,p.toString(2));if(!p.getString("status").equals("pending")||p.optBoolean("expired")||p.optBoolean("invalidated"))continue;
    String id=p.getString("id");for(boolean approve:new boolean[]{true,false}){Button decision=button(approvalsBox,approve?"Approve exact action":"Reject action",()->{});decision.setOnClickListener(v->confirm(approve?"Approve this bound action?":"Reject this action?",p.optString("actor_name")+" · "+p.optString("resource")+"\n"+p.optString("canonical_payload"),()->run(decision,()->client.decide(id,approve),reply->home())));}
   }
  });
 }
 @Override protected void onDestroy(){gate.advance();api=null;worker.shutdownNow();stopWorker.shutdownNow();super.onDestroy();}
 @Override public void onBackPressed(){setup();}
}
