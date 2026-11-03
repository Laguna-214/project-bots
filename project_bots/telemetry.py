"""Read-only Linux utilization sensors; never evidence of isolation or GPU offload."""
from pathlib import Path
import re
import time


def collect_metrics(proc_root=Path('/proc'), drm_root=Path('/sys/class/drm'), *, interval=.05, sleep=time.sleep):
    if not 0 < interval <= 1:
        raise ValueError('Sensor interval must be between zero and one second')
    result={'observed_at':time.time(), 'sample_interval_seconds':interval,
            'cpu':{'status':'unavailable','busy_percent':None},'gpus':[], 'gpu_status':'unavailable',
            'notice':'Read-only host utilization is not proof of model GPU offload, agent isolation or security monitoring.'}
    def cpu_ticks():
        line=next(line for line in (Path(proc_root)/'stat').read_text().splitlines() if line.startswith('cpu '))
        ticks=[int(value) for value in line.split()[1:9]]
        if len(ticks)<4 or any(value<0 for value in ticks): raise ValueError('Invalid CPU counters')
        return sum(ticks), ticks[3]+(ticks[4] if len(ticks)>4 else 0)
    try:
        before=cpu_ticks(); sleep(interval); after=cpu_ticks()
        total=after[0]-before[0]; idle=after[1]-before[1]
        if total<=0 or not 0<=idle<=total: raise ValueError('CPU sample did not advance')
        result['cpu']={'status':'available','busy_percent':round(100*(total-idle)/total,3)}
    except (OSError,ValueError,StopIteration) as exc:
        result['cpu']['error_kind']=type(exc).__name__
    try:
        cards=sorted(p for p in Path(drm_root).iterdir() if re.fullmatch(r'card[0-9]+',p.name))
    except OSError:
        cards=[]
    for card in cards:
        device=card/'device'
        try:
            if (device/'vendor').read_text().strip().lower()!='0x1002': continue
        except OSError:
            continue
        item={'card':card.name,'vendor':'AMD','status':'unavailable', 'busy_percent':None,
              'vram_total_bytes':None,'vram_used_bytes':None}
        for filename,key in [('gpu_busy_percent','busy_percent'),('mem_info_vram_total','vram_total_bytes'),('mem_info_vram_used','vram_used_bytes')]:
            try:
                value=int((device/filename).read_text().strip())
                if value<0 or (key=='busy_percent' and value>100): raise ValueError('Invalid sensor value')
                item[key]=value
            except (OSError,ValueError): pass
        if item['vram_total_bytes'] is not None and item['vram_used_bytes'] is not None and item['vram_used_bytes']>item['vram_total_bytes']:
            item['vram_used_bytes']=None
        present=sum(item[key] is not None for key in ('busy_percent','vram_total_bytes','vram_used_bytes'))
        item['status']='available' if present==3 else ('partial' if present else 'unavailable')
        result['gpus'].append(item)
    if result['gpus']:
        result['gpu_status']='available' if all(g['status']=='available' for g in result['gpus']) else 'partial'
    return result
