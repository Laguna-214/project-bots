package app.projectbots;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;

/** Only network boundary. No global cookie handler, TLS override, redirect or resource loader. */
final class NativeTransport {
 static final int MAX_RESPONSE=1024*1024, MAX_REQUEST=65536;
 private static final java.util.concurrent.ScheduledExecutorService DEADLINES=java.util.concurrent.Executors.newSingleThreadScheduledExecutor(r->{Thread t=new Thread(r,"native-http-deadline");t.setDaemon(true);return t;});
 private final String origin;
 private final int connectTimeout,readTimeout,totalTimeout;
 NativeTransport(String origin){this(origin,5000,10000,20000);}
 NativeTransport(String origin,int connectTimeout,int readTimeout){this(origin,connectTimeout,readTimeout,20000);}
 NativeTransport(String origin,int connectTimeout,int readTimeout,int totalTimeout){
  String parsed=Endpoint.parse(origin);
  if(parsed==null||!parsed.equals(origin))throw new IllegalArgumentException("Invalid backend origin");
  this.origin=origin;this.connectTimeout=connectTimeout;this.readTimeout=readTimeout;this.totalTimeout=totalTimeout;
 }
 String request(String method,String path,String body,String token,String csrf)throws IOException{
  if(!method.equals("GET")&&!method.equals("POST"))throw new IOException("Unsupported method");
  if(path==null||!path.startsWith("/")||path.startsWith("//")||path.contains("\\")||path.contains("#")||path.matches(".*[\\x00-\\x20].*"))throw new IOException("Invalid API path");
  if((method.equals("POST"))!=(body!=null))throw new IOException("Invalid request body");
  byte[] bytes=body==null?null:body.getBytes(StandardCharsets.UTF_8);
  if(bytes!=null&&bytes.length>MAX_REQUEST)throw new IOException("Request exceeds 64 KiB");
  HttpURLConnection c=(HttpURLConnection)new URL(origin+path).openConnection(Proxy.NO_PROXY);
  c.setInstanceFollowRedirects(false);c.setUseCaches(false);c.setConnectTimeout(connectTimeout);c.setReadTimeout(readTimeout);c.setRequestMethod(method);
  c.setRequestProperty("Accept","application/json");c.setRequestProperty("Accept-Encoding","identity");c.setRequestProperty("Cache-Control","no-store");
  c.setRequestProperty("X-Setup-Origin",origin);c.setRequestProperty("Origin",origin);
  if(token!=null&&!token.isEmpty())c.setRequestProperty("Authorization","Bearer "+token);
  if(csrf!=null&&!csrf.isEmpty())c.setRequestProperty("X-CSRF-Token",csrf);
  long deadline=System.nanoTime()+java.util.concurrent.TimeUnit.MILLISECONDS.toNanos(totalTimeout);
  java.util.concurrent.ScheduledFuture<?> timeout=DEADLINES.schedule(c::disconnect,totalTimeout,java.util.concurrent.TimeUnit.MILLISECONDS);
  try{
   if(bytes!=null){c.setDoOutput(true);c.setFixedLengthStreamingMode(bytes.length);c.setRequestProperty("Content-Type","application/json");try(OutputStream out=c.getOutputStream()){out.write(bytes);}}
   int status=c.getResponseCode();
   if(status>=300&&status<400)throw new IOException("Redirect rejected; backend origin unchanged");
   if(status<200||status>=300)throw new IOException("Backend HTTP "+status+"; action outcome may be uncertain");
   if(c.getContentLengthLong()>MAX_RESPONSE)throw new IOException("Response exceeds 1 MiB");
   try(InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
    byte[] chunk=new byte[8192];int n;
    while((n=in.read(chunk))!=-1){if(System.nanoTime()>deadline||out.size()+n>MAX_RESPONSE)throw new IOException("Response bound exceeded");out.write(chunk,0,n);}
    return out.toString("UTF-8");
   }
  }finally{timeout.cancel(false);c.disconnect();}
 }
}
