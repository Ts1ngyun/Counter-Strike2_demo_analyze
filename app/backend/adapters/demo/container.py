"""PBDEMS2 framing only, not a replacement for entity decoding."""
import mmap, struct
from pathlib import Path
import pandas as pd
import snappy

def varint(buf,pos):
    v=0
    for s in range(0,70,7):
        if pos>=len(buf): raise ValueError('截断 varint')
        b=buf[pos];pos+=1;v|=(b&127)<<s
        if b<128:return v,pos
    raise ValueError('非法 varint')

def fields(buf):
    p=0
    while p<len(buf):
        tag,p=varint(buf,p);n,w=tag>>3,tag&7
        if w==0:v,p=varint(buf,p)
        elif w in (1,5):
            size=8 if w==1 else 4; v=buf[p:p+size]; p+=size
        elif w==2:
            size,p=varint(buf,p);v=buf[p:p+size];p+=size
        else:raise ValueError('不支持的 protobuf wire')
        if p>len(buf):raise ValueError('截断 protobuf')
        yield n,w,v

def scan(path,out,cancel=lambda:None):
    rows=[];info={};max_tick=0;count=0;seen_stop=False
    with open(path,'rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as b:
        if len(b)<16 or b[:8]!=b'PBDEMS2\0':raise ValueError('不是 PBDEMS2 demo')
        for off in struct.unpack('<II',b[8:16]):
            if off and not 16<=off<len(b):raise ValueError('容器头偏移越界')
        p=16
        while p<len(b):
            off=p;raw,p=varint(b,p);tick,p=varint(b,p);size,p=varint(b,p)
            if p+size>len(b):raise ValueError(f'容器截断：命令偏移 {off}')
            tick=(tick&0xffffffff)-(0x100000000 if tick&0x80000000 else 0)
            cmd=raw&~64
            rows.append({'sequence':count,'tick':tick,'command_id':cmd,'offset':off,'body_offset':p,'stored_bytes':size,'compressed':bool(raw&64)})
            if cmd==0:seen_stop=True
            if cmd==2:
                body=b[p:p+size]
                if raw&64:body=snappy.decompress(body)
                for n,w,v in fields(body):
                    if n==1 and w==5:info['playback_seconds']=struct.unpack('<f',v)[0]
                    if n==2 and w==0:info['playback_ticks']=v
            max_tick=max(max_tick,tick);count+=1;p+=size
            if count%10000==0:cancel()
        if not seen_stop:raise ValueError('缺少 DEM_Stop：文件可能尚未录制完成或已截断')
    Path(out).mkdir(parents=True,exist_ok=True);pd.DataFrame(rows).to_parquet(Path(out)/'0000.parquet',index=False)
    return {**info,'last_command_tick':max_tick,'command_count':count,'complete_container':True}
