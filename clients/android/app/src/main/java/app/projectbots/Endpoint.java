package app.projectbots;
import java.net.URI;
public final class Endpoint {
 private Endpoint() {}
 public static String parse(String value) {
  try {
   if(value==null||!value.equals(value.trim())||value.matches(".*[\\\\\\s\\x00-\\x1f].*"))return null;
   URI u=new URI(value);
   String scheme=u.getScheme(),host=u.getHost(),path=u.getRawPath();
   if(host==null||u.getRawUserInfo()!=null||u.getRawQuery()!=null||u.getRawFragment()!=null||!(path.isEmpty()||path.equals("/")))return null;
   if(u.getPort() < -1 || u.getPort()>65535 || u.getPort()==0)return null;
   boolean local=host.equals("localhost")||host.equals("127.0.0.1")||host.equals("[::1]");
   if(!"https".equals(scheme)&&!("http".equals(scheme)&&local))return null;
   int port=u.getPort(); if(("https".equals(scheme)&&port==443)||("http".equals(scheme)&&port==80))port=-1;
   return scheme+"://"+host.toLowerCase(java.util.Locale.ROOT)+(port==-1?"":":"+port);
  } catch(Exception e) {return null;}
 }
 public static boolean allows(String origin,String value) {
  try {URI u=new URI(value);return u.getRawUserInfo()==null&&origin.equals(parse(u.getScheme()+"://"+u.getRawAuthority()));}catch(Exception e){return false;}
 }
}
