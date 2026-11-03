"""Opt-in trusted runner for the ONE existing inference broker; never a model server.

Run: python3 -m project_bots.chat_runner --db PATH --broker http://127.0.0.1:21435
Only independent inference credentials from agent config are sent to the broker.
"""
import argparse
import json
import os
import threading
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from .chat import ChatService
from .conversations import ConversationService
from .service import ConflictError
from .security import check_agent_execution


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class ChatRunner:
    def __init__(self, repository, broker, *, timeout=60):
        parsed=urlsplit(broker)
        if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1','localhost','::1') or not parsed.port or parsed.path not in ('','/') or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Explicit local shared broker required')
        if not 0 < timeout <= 300:
            raise ValueError('Invalid deadline')
        self.repository=repository
        self.service=ConversationService(repository)
        self.broker=broker.rstrip('/')
        self.timeout=timeout
        self.opener=build_opener(ProxyHandler({}),NoRedirect())

    def recover(self):
        """Explicit offline recovery only: prior running requests are uncertain.

        Do not run while another runner is active; uncertain jobs never auto-retry.
        """
        with self.repository.transaction() as db:
            return db.execute("UPDATE conversation_jobs SET status='uncertain',updated_at=? WHERE status IN ('running','cancelling')",(time.time(),)).rowcount

    def context(self, db, job):
        check_agent_execution(self.repository,job['agent_id'],db=db)
        current=db.execute('SELECT * FROM conversation_jobs WHERE id=?',(job['id'],)).fetchone()
        config_row=db.execute('SELECT data FROM conversation_agents WHERE agent_id=?',(job['agent_id'],)).fetchone()
        identity=db.execute('SELECT * FROM chat_identities WHERE agent_id=?',(job['agent_id'],)).fetchone()
        member=db.execute('SELECT 1 FROM chat_members WHERE chat_id=? AND agent_id=?',(job['chat_id'],job['agent_id'])).fetchone()
        if not current or current['status'] != 'running' or not config_row or not identity or not identity['enabled'] or not member:
            raise ConflictError('Reply revoked')
        config=json.loads(config_row[0])
        if not config['enabled'] or config['revision'] != job['revision']:
            raise ConflictError('Enrollment changed')
        chat=ChatService.require_chat(db,job['chat_id'])
        agent=json.loads(db.execute('SELECT data FROM agents WHERE id=?',(job['agent_id'],)).fetchone()[0])
        worker=json.loads(db.execute('SELECT data FROM workers WHERE agent_id=?',(job['agent_id'],)).fetchone()[0])
        ref=agent.get('config',{}).get('credential_env')
        token=os.environ.get(ref or '', '')
        settings_row=db.execute('SELECT data FROM settings WHERE id=1').fetchone()
        settings=json.loads(settings_row[0]) if settings_row else {}
        protected={settings.get('machine_api_env','PROJECT_BOTS_API_TOKEN'),'PROJECT_BOTS_COMPUTE_TOKEN','PROJECT_BOTS_INFERENCE_ADMIN_TOKEN','PROJECT_BOTS_LLAMA_BACKEND_TOKEN',os.environ.get('PROJECT_BOTS_LLAMA_TOKEN_ENV','')}
        for table in ('workers','machines'):
            protected.update(json.loads(r[0]).get('credential_env','') for r in db.execute('SELECT data FROM '+table))
        protected.update(r[0] for r in db.execute('SELECT credential_env FROM chat_identities'))
        # Gateway and control-plane credentials may never become inference auth.
        if not ref or len(token)<32 or ref in protected or any(token == os.environ.get(r,'') for r in protected) or token == os.environ.get(identity['credential_env'],''):
            raise ConflictError('Independent inference credential required')
        if chat['kind']=='group':
            public_identity = json.dumps({'name':agent['name'], 'role':agent['role']}, ensure_ascii=False)
            system='You are the group participant with this public identity: '+public_identity+'. Reply only with a public final answer to the shared messages. Do not disclose private reasoning. No tools are available.'
        else:
            system=config['system_instructions']+'\nPrivate memory:\n'+config['memory']+'\nReturn only the final answer. No tools are available.'
        rows=db.execute("SELECT m.sender,m.content FROM chat_messages m LEFT JOIN conversation_jobs j ON j.id=m.client_id AND j.agent_id=m.sender AND j.chat_id=m.chat_id WHERE m.chat_id=? AND (m.sequence<=? OR (j.trigger_sequence=? AND j.status='completed')) ORDER BY m.sequence DESC LIMIT 40",(job['chat_id'],job['trigger_sequence'],job['trigger_sequence'])).fetchall()
        messages=[{'role':'system','content':system}]
        # Peer messages are untrusted quoted user data, never system/tool roles.
        messages += [{'role':'assistant' if r['sender']==job['agent_id'] else 'user','content':r['content']} for r in reversed(rows)]
        body={'model':worker['profile']['model'],'messages':messages,'stream':False,'tools':[],'tool_choice':'none'}
        if len(json.dumps(body,ensure_ascii=False).encode())+256+worker['profile']['max_output'] > worker['profile']['context']:
            raise ConflictError('Context budget exceeded')
        return body,token

    def post(self, path, body, token, request_id):
        req=Request(self.broker+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+token,'X-Request-ID':request_id})
        with self.opener.open(req,timeout=self.timeout) as response:
            raw=response.read(1024*1024+1)
            if len(raw)>1024*1024:
                raise ValueError('Reply exceeds bound')
            return json.loads(raw)

    def run_once(self):
        with self.repository.transaction() as db:
            # Serialize each agent's history, even across independent processes.
            row=db.execute("SELECT * FROM conversation_jobs j WHERE status='queued' AND NOT EXISTS (SELECT 1 FROM conversation_jobs a WHERE a.agent_id=j.agent_id AND a.status IN ('running','cancelling','uncertain')) ORDER BY created_at LIMIT 1").fetchone()
            if not row:
                return False
            job=dict(row)
            db.execute("UPDATE conversation_jobs SET status='running',updated_at=? WHERE id=?",(time.time(),job['id']))
        sent=False
        stopped=threading.Event()
        revoked=threading.Event()
        token=None
        def watch():
            while not stopped.wait(.05):
                try:
                    with self.repository.transaction() as db:
                        self.context(db,job)
                except Exception:
                    revoked.set()
                    try:
                        self.post('/v1/requests/cancel',{'request_id':job['id']},token,job['id'])
                    except Exception:
                        pass
                    return
        watcher=None
        try:
            with self.repository.transaction() as db:
                body,token=self.context(db,job)
            watcher=threading.Thread(target=watch,daemon=True)
            watcher.start()
            sent=True
            response=self.post('/v1/chat/completions',body,token,job['id'])
            message=response['choices'][0]['message']
            content=message.get('content')
            if not isinstance(content,str) or not content.strip() or len(content)>16000 or message.get('tool_calls') or any(tag in content.lower() for tag in ('<think','</think','<analysis','</analysis','[analysis]')):
                raise ValueError('Only bounded final text accepted')
            with self.repository.transaction() as db:
                self.context(db,job)
                if revoked.is_set():
                    raise ConflictError('Reply revoked')
                db.execute('INSERT INTO chat_messages(chat_id,sender,client_id,content,created_at) VALUES (?,?,?,?,?)',(job['chat_id'],job['agent_id'],job['id'],content,time.time()))
                db.execute("UPDATE conversation_jobs SET status='completed',updated_at=? WHERE id=?",(time.time(),job['id']))
        except Exception:
            with self.repository.transaction() as db:
                db.execute("UPDATE conversation_jobs SET status=?,updated_at=? WHERE id=? AND status IN ('running','cancelling')",('uncertain' if sent else 'blocked',time.time(),job['id']))
        finally:
            stopped.set()
            if watcher:
                watcher.join(self.timeout+1)
        return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',required=True)
    parser.add_argument('--broker',required=True)
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--recover-offline',action='store_true')
    args=parser.parse_args()
    from .repository import SQLiteRepository
    runner=ChatRunner(SQLiteRepository(args.db),args.broker)
    if args.recover_offline:
        print('Uncertain jobs:',runner.recover())
        return
    try:
        while True:
            ran=runner.run_once()
            if args.once:
                break
            if not ran:
                time.sleep(.5)
    except KeyboardInterrupt:
        pass


if __name__=='__main__':
    main()
