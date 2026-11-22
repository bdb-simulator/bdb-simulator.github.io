# 영역(패·드롭·덱 등)의 카드를 고르는 처리에 쓰인 필터 키 중 defMatches가 처리하지 않는 것
import json,re
H='/home/claude/bdb-simulator/simulator/index.html'; code=open(H,encoding='utf-8').read()
def body(name):
    i=code.index('function '+name+'('); j=code.index('{',i); dep=0
    for k in range(j,len(code)):
        if code[k]=='{': dep+=1
        elif code[k]=='}':
            dep-=1
            if dep==0: return code[j:k]
dm=body('defMatches')
handled=set(re.findall(r"f\??\.(\w+)",dm))
db=json.load(open(H.replace('index.html','cards_db.json')))['defs']
res={}
def zone_ctx(st):
    op=st.get('op')
    if op=='tgt' and st.get('zone') and st.get('zone')!='field': return True
    if op in ('pick','playFree','search','revealTop','discard','lookTop','look','tutor','addHand','fromDrop') and st.get('from','hand')!='field': return True
    return False
def walk(steps,cid):
    for st in steps or []:
        if not isinstance(st,dict): continue
        f=st.get('f')
        if isinstance(f,dict) and zone_ctx(st):
            for k in f:
                if k not in handled and k not in ('side',): res.setdefault((st['op'],k),set()).add(cid)
        for v in st.values():
            if isinstance(v,list) and v and isinstance(v[0],dict): walk(v,cid)
            if isinstance(v,list) and v and isinstance(v[0],list):
                for o in v: walk(o,cid)
for cid,d in db.items():
    for a in d.get('ab',[]): walk(a.get('do'),cid); walk(a.get('cost'),cid)
for (op,k),c in sorted(res.items()): print(op,k,len(c),sorted(c)[:6])
