package app.projectbots;
public final class EndpointTest {
 public static void main(String[] args) {
 String[] good={"https://bots.example", "https://192.168.1.4:8443", "http://127.0.0.1:8765", "http://localhost:8765", "http://[::1]:8765"};
 String[] bad={"http://192.168.1.4", "http://127.1", "http://2130706433", "https://u:p@bots.example", "https://bots.example/path", "https://bots.example?key=x", "https://bots.example#x", "file:///tmp/a", "javascript:1", "https://bots.example\\@evil.example", " https://bots.example", "https://bots.example\n"};
 for(String s:good) if(Endpoint.parse(s)==null) throw new AssertionError(s);
 for(String s:bad) if(Endpoint.parse(s)!=null) throw new AssertionError(s);
 if(!Endpoint.allows("https://bots.example", "https://bots.example/api/session"))throw new AssertionError("same-origin");
 for(String s:new String[]{"file:///tmp/a","javascript:1","https://u:p@bots.example","http://bots.example","https://evil.example/"})if(Endpoint.allows("https://bots.example",s))throw new AssertionError("allowed: "+s);
 if(Endpoint.allows("https://bots.example", "https://evil.example/"))throw new AssertionError("cross-origin");
 if(!"https://bots.example".equals(Endpoint.parse("https://bots.example:443/")))throw new AssertionError("default HTTPS port canonicalization");
 if(!Endpoint.allows("https://bots.example", "https://bots.example:443/api/session"))throw new AssertionError("default port origin");
 System.out.println("Android endpoint URL and origin isolation tests passed");
 }
}
