package app.projectbots;

import com.sun.net.httpserver.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicInteger;

/** Real sockets, two independently observed origins; no request-handler mocks. */
public final class TransportTest {
 static void check(boolean b,String m){if(!b)throw new AssertionError(m);}
 interface Action {void run() throws Exception;}
 static void denied(Action a)throws Exception{try{a.run();throw new AssertionError("expected rejection");}catch(java.io.IOException expected){}}
 public static void main(String[] args)throws Exception{
  AtomicInteger contacts=new AtomicInteger();
  HttpServer second=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
  second.createContext("/",x->{contacts.incrementAndGet();x.sendResponseHeaders(200,0);x.close();});second.start();
  HttpServer first=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
  first.createContext("/",x->{
   try{
    String p=x.getRequestURI().getPath();
    if(p.startsWith("/redirect/")){x.getResponseHeaders().add("Location","http://127.0.0.1:"+second.getAddress().getPort()+"/stolen");x.sendResponseHeaders(Integer.parseInt(p.substring(10)),-1);}
    else if(p.equals("/large")){x.sendResponseHeaders(200,NativeTransport.MAX_RESPONSE+1);try{x.getResponseBody().write(new byte[NativeTransport.MAX_RESPONSE+1]);}catch(Exception ignored){}}
    else if(p.equals("/chunked")){x.sendResponseHeaders(200,0);try{x.getResponseBody().write(new byte[NativeTransport.MAX_RESPONSE+1]);}catch(Exception ignored){}}
    else if(p.equals("/drip")){x.sendResponseHeaders(200,0);try{for(int i=0;i<30;i++){x.getResponseBody().write('x');x.getResponseBody().flush();Thread.sleep(40);}}catch(Exception ignored){}}
    else if(p.equals("/slow")){Thread.sleep(600);x.sendResponseHeaders(200,-1);}
    else {String body=new String(x.getRequestBody().readAllBytes(),StandardCharsets.UTF_8);String text=x.getRequestMethod()+"|"+body+"|"+x.getRequestHeaders().getFirst("Authorization")+"|"+x.getRequestHeaders().getFirst("X-CSRF-Token")+"|"+x.getRequestHeaders().getFirst("Origin");byte[] out=text.getBytes(StandardCharsets.UTF_8);x.sendResponseHeaders(200,out.length);x.getResponseBody().write(out);}
   }catch(Exception ignored){}finally{x.close();}
  });first.start();
  try{
   String origin="http://127.0.0.1:"+first.getAddress().getPort();NativeTransport t=new NativeTransport(origin,200,200);
   for(int status=300;status<400;status++)for(String method:new String[]{"GET","POST"}){final int code=status;denied(()->t.request(method,"/redirect/"+code,"POST".equals(method)?"{\"script\":\"https://other/evil.js\"}":null,"fixture-token","fixture-csrf"));}
   check(contacts.get()==0,"second origin contacted");
   String body="{\"content\":\"persistent body Ω\"}";
   check(t.request("POST","/echo",body,"fixture-token","fixture-csrf").equals("POST|"+body+"|Bearer fixture-token|fixture-csrf|"+origin),"POST changed method/body/auth/CSRF/origin");
   denied(()->t.request("GET","//127.0.0.1:"+second.getAddress().getPort(),null,"", ""));
   denied(()->t.request("DELETE","/echo",null,"", ""));
   denied(()->t.request("POST","/echo","x".repeat(65537),"", ""));
   denied(()->t.request("GET","/large",null,"", ""));
   denied(()->t.request("GET","/chunked",null,"", ""));
   NativeTransport shortDeadline=new NativeTransport(origin,200,200,150);
   denied(()->shortDeadline.request("GET","/drip",null,"", ""));
   long start=System.nanoTime();denied(()->t.request("GET","/slow",null,"", ""));check((System.nanoTime()-start)/1e6<2000,"timeout not bounded");
   check(contacts.get()==0,"second origin contacted after all cases");
   System.out.println("PASS real two-origin GET/script-analogue + POST ALL 30x rejection; ZERO second-origin contacts; exact method/body/headers; bounds/timeouts");
  }finally{first.stop(0);second.stop(0);}
 }
}
