package app.projectbots;

import android.app.Instrumentation;
import android.app.Activity;
import android.os.Bundle;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;

/** No dependency downloads. Must be RUN on Android; compilation is not acceptance. */
public final class NativeRegressionInstrumentation extends Instrumentation {
 @Override public void onCreate(Bundle args){super.onCreate(args);start();}
 private static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
 private static final class Fixture implements AutoCloseable {
  final ServerSocket socket;final AtomicInteger contacts=new AtomicInteger();final Thread thread;
  volatile String observed="";volatile int redirectPort;volatile boolean activityFailure;
  Fixture()throws IOException{
   socket=new ServerSocket(0,8,InetAddress.getByName("127.0.0.1"));
   thread=new Thread(()->{while(!socket.isClosed())try(Socket s=socket.accept()){
    contacts.incrementAndGet();s.setSoTimeout(3000);InputStream in=s.getInputStream();String first=line(in);Map<String,String> headers=new HashMap<>();String l;
    while(!(l=line(in)).isEmpty()){int i=l.indexOf(':');if(i>0)headers.put(l.substring(0,i).toLowerCase(Locale.ROOT),l.substring(i+1).trim());}
    int length=Integer.parseInt(headers.getOrDefault("content-length","0"));byte[] body=new byte[length];int read=0;while(read<length){int n=in.read(body,read,length-read);if(n<0)throw new EOFException();read+=n;}
    observed=first+"|"+new String(body,StandardCharsets.UTF_8)+"|"+headers.get("authorization")+"|"+headers.get("x-csrf-token")+"|"+headers.get("origin");
    String path=first.split(" ")[1];String response;
    if(path.startsWith("/r/"))response="HTTP/1.1 "+path.substring(3)+" Redirect\r\nLocation: http://127.0.0.1:"+redirectPort+"/forbidden.js\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
    else if(activityFailure&&(path.equals("/api/jobs")||path.equals("/api/security/events")||path.equals("/api/approvals")))response="HTTP/1.1 503 Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
    else {String payload=path.equals("/api/security/status")?"{\"agents\":[{\"agent_id\":\"11111111-1111-1111-1111-111111111111\"}]}":"{}";response="HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "+payload.getBytes(StandardCharsets.UTF_8).length+"\r\nConnection: close\r\n\r\n"+payload;}
    s.getOutputStream().write(response.getBytes(StandardCharsets.UTF_8));
   }catch(IOException e){if(!socket.isClosed())observed="fixture IO failure";}},"native-fixture");thread.start();
  }
  static String line(InputStream in)throws IOException{ByteArrayOutputStream out=new ByteArrayOutputStream();int b;while((b=in.read())!=-1){if(b=='\n')return out.toString("UTF-8").replace("\r","");if(out.size()>8192)throw new IOException("header too long");out.write(b);}throw new EOFException();}
  public void close()throws Exception{socket.close();thread.join(5000);}
 }
 private static java.lang.reflect.Field activityField(String name)throws Exception{java.lang.reflect.Field f=MainActivity.class.getDeclaredField(name);f.setAccessible(true);return f;}
 private static boolean hasLabel(android.view.View v,String label){
  if(v instanceof android.widget.TextView&&((android.widget.TextView)v).getText().toString().equals(label))return true;
  if(v instanceof android.view.ViewGroup)for(int i=0;i<((android.view.ViewGroup)v).getChildCount();i++)if(hasLabel(((android.view.ViewGroup)v).getChildAt(i),label))return true;
  return false;
 }
 private void activityAvailability()throws Exception{
  try(Fixture fixture=new Fixture()){
   fixture.activityFailure=true;
   MainActivity activity=(MainActivity)startActivitySync(new android.content.Intent(getTargetContext(),MainActivity.class).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK));
   java.util.concurrent.atomic.AtomicReference<Throwable> failure=new java.util.concurrent.atomic.AtomicReference<>();
   try{
    runOnMainSync(()->{try{
     activityField("api").set(activity,new BackendApi("http://127.0.0.1:"+fixture.socket.getLocalPort()));activityField("screen").set(activity,"Activity");
     java.lang.reflect.Method home=MainActivity.class.getDeclaredMethod("home");home.setAccessible(true);home.invoke(activity);
     check(hasLabel((android.view.View)activityField("page").get(activity),"Emergency stop ALL"),"global stop requires informational response");
    }catch(Throwable e){failure.set(e);}});
    if(failure.get()!=null)throw new AssertionError(failure.get());
    long deadline=System.nanoTime()+java.util.concurrent.TimeUnit.SECONDS.toNanos(5);java.util.concurrent.atomic.AtomicBoolean agent=new java.util.concurrent.atomic.AtomicBoolean();
    while(!agent.get()&&System.nanoTime()<deadline){waitForIdleSync();runOnMainSync(()->{try{android.view.View page=(android.view.View)activityField("page").get(activity);check(hasLabel(page,"Emergency stop ALL"),"failed sections removed global stop");agent.set(hasLabel(page,"Stop agent 11111111-1111-1111-1111-111111111111")&&hasLabel(page,"Jobs failed; refresh required. Global stop remains available; no automatic retry.")&&hasLabel(page,"Events failed; refresh required. Global stop remains available; no automatic retry.")&&hasLabel(page,"Approvals failed; refresh required. Global stop remains available; no automatic retry."));}catch(Throwable e){failure.set(e);}});Thread.sleep(20);}
    if(failure.get()!=null)throw new AssertionError(failure.get());check(agent.get(),"security success did not render per-agent stop after jobs/events/approvals failures");
   }finally{runOnMainSync(activity::finish);}
  }
 }
 @Override public void onStart(){Bundle result=new Bundle();try{
  activityAvailability();
  try(Fixture first=new Fixture();Fixture second=new Fixture()){
   first.redirectPort=second.socket.getLocalPort();String origin="http://127.0.0.1:"+first.socket.getLocalPort();NativeTransport transport=new NativeTransport(origin);
   for(int status=300;status<400;status++)for(String method:new String[]{"GET","POST"}){
    boolean rejected=false;try{transport.request(method,"/r/"+status,method.equals("POST")?"{\"code\":\"00000000\"}":null,"fixture-only","csrf-only");}catch(IOException expected){rejected=true;}check(rejected,"redirect accepted");
   }
   check(second.contacts.get()==0,"forbidden origin contacted");
   String body="{\"content\":\"native exact body\"}";transport.request("POST","/echo",body,"fixture-only","csrf-only");
   check(first.observed.equals("POST /echo HTTP/1.1|"+body+"|Bearer fixture-only|csrf-only|"+origin),"Android changed method/body/auth/CSRF/origin");
  }
  SelectionGate gate=new SelectionGate();long old=gate.advance();gate.advance();gate.advance();check(!gate.current(old),"ABA response accepted");
  result.putString("stream","PASS Android real sockets: all redirect rejection, zero second-origin contacts, exact POST headers/body, selection ABA\n");finish(Activity.RESULT_OK,result);
 }catch(Throwable e){result.putString("stream","FAIL "+e.getClass().getSimpleName()+": "+e.getMessage()+"\n");finish(Activity.RESULT_CANCELED,result);}}
}
