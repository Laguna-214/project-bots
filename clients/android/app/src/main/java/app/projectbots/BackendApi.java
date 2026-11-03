package app.projectbots;
import org.json.*;
import java.io.IOException;

/** Presentation adapter only: backend owns identities, history, validation and authorization. */
final class BackendApi {
 private final NativeTransport transport;
 private String token="",csrf="";
 BackendApi(String origin){transport=new NativeTransport(origin);}
 static JSONObject object(String s)throws JSONException{return new JSONObject(s);}
 static String id(String s)throws IOException{
  if(s==null||!s.matches("[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}"))throw new IOException("Invalid resource identity");return s;
 }
 private String get(String path)throws IOException{return transport.request("GET",path,null,token,csrf);}
 private JSONObject post(String path,JSONObject body)throws IOException,JSONException{return object(transport.request("POST",path,body.toString(),token,csrf));}
 void pair(String code)throws Exception{
  if(!code.matches("[0-9]{8}"))throw new IOException("Enter the exact eight-digit console pairing code");
  token=post("/api/pair",new JSONObject().put("code",code)).getString("token");
  csrf=object(get("/api/session")).getString("csrf");
 }
 JSONArray agents()throws Exception{return new JSONArray(get("/api/agents"));}
 JSONObject createAgent(String name,String role,String model)throws Exception{
  JSONObject config=new JSONObject();if(!model.isEmpty())config.put("model",model);
  return post("/api/agents",new JSONObject().put("name",name).put("role",role).put("config",config).put("machine_id",JSONObject.NULL));
 }
 JSONArray chats()throws Exception{return new JSONArray(get("/api/chats"));}
 JSONObject createChat(String title,String kind,JSONArray members)throws Exception{return post("/api/chats",new JSONObject().put("title",title).put("kind",kind).put("agent_ids",members));}
 JSONObject members(String chat,JSONArray members)throws Exception{return post("/api/chats/"+id(chat)+"/members",new JSONObject().put("agent_ids",members));}
 JSONObject history(String chat,long after)throws Exception{
  if(after<0)throw new IOException("Invalid cursor");return object(get("/api/chats/"+id(chat)+"/messages?after="+after));
 }
 JSONObject send(String chat,String clientId,String content)throws Exception{return post("/api/chats/"+id(chat)+"/messages",new JSONObject().put("client_id",id(clientId)).put("content",content));}
 JSONArray jobs()throws Exception{return new JSONArray(get("/api/jobs"));}
 JSONObject security()throws Exception{return object(get("/api/security/status"));}
 JSONObject events()throws Exception{return object(get("/api/security/events"));}
 JSONObject approvals()throws Exception{return object(get("/api/approvals"));}
 JSONObject decide(String proposal,boolean approve)throws Exception{return post("/api/approvals/"+id(proposal)+(approve?"/approve":"/reject"),new JSONObject());}
 JSONObject stopAgent(String agent)throws Exception{return post("/api/security/incidents",new JSONObject().put("agent_id",id(agent)).put("severity","high").put("behavior","Administrator requested agent stop").put("resource","worker runtime and communication").put("evidence","Explicit native Android confirmation"));}
 JSONObject stopAll()throws Exception{return post("/api/security/emergency-stop",new JSONObject().put("reason","Administrator emergency stop from native Android confirmation"));}
}
