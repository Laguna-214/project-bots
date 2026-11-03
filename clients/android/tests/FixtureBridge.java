package app.projectbots;
import java.io.*;
import java.util.Base64;
/** Test process adapter. Credentials travel only anonymous pipes, never argv/logs. */
public final class FixtureBridge {
 public static void main(String[] args)throws Exception{
  NativeTransport t=new NativeTransport(args[0],500,500);BufferedReader in=new BufferedReader(new InputStreamReader(System.in));String line;
  while((line=in.readLine())!=null){String[] p=line.split("\\t",-1);try{
   String body=p[2].isEmpty()?null:new String(Base64.getDecoder().decode(p[2]),java.nio.charset.StandardCharsets.UTF_8);
   String response=t.request(p[0],p[1],body,p[3],p[4]);System.out.println("OK\t"+Base64.getEncoder().encodeToString(response.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
  }catch(Exception e){System.out.println("ERR\t"+e.getClass().getSimpleName());}}
 }
}
