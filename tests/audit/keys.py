# 카드 데이터(cards_db.json)에 쓰인 op·파라미터·필터·조건 키 중 엔진 코드가 한 번도 읽지 않는 것을 찾음
import json, re, sys, collections
H='/home/claude/bdb-simulator/simulator/index.html'
code=open(H,encoding='utf-8').read()
code=code[code.index('<script>'):]
db=json.load(open(H.replace('index.html','cards_db.json')))['defs']
ops=collections.defaultdict(lambda: collections.defaultdict(set))   # op -> key -> cards
filt=collections.defaultdict(set); conds=collections.defaultdict(set); abkeys=collections.defaultdict(set)
FILTER_KEYS={'f','to','from','who'}
def walk_f(f,cid):
    if isinstance(f,dict):
        for k,v in f.items():
            filt[k].add(cid)
            if k in ('or','and','not') : 
                for g in (v if isinstance(v,list) else [v]): walk_f(g,cid)
    elif isinstance(f,list):
        for g in f: walk_f(g,cid)
def walk_cond(c,cid):
    if isinstance(c,list):
        for x in c: walk_cond(x,cid)
    elif isinstance(c,dict):
        for k,v in c.items():
            conds[k].add(cid)
            if k in ('or','and','not'): walk_cond(v,cid)
def walk_steps(steps,cid):
    for st in steps or []:
        if not isinstance(st,dict): continue
        op=st.get('op','?')
        for k,v in st.items():
            ops[op][k].add(cid)
            if k=='f': walk_f(v,cid)
            if k=='to' and isinstance(v,dict):
                for kk,vv in v.items():
                    ops[op]['to.'+kk].add(cid)
                    if isinstance(vv,dict): walk_f(vv,cid)
            if k in ('if','cond','c'): walk_cond(v,cid)
            if isinstance(v,list) and v and isinstance(v[0],dict) and 'op' in v[0]: walk_steps(v,cid)
            if isinstance(v,list) and v and isinstance(v[0],list): 
                for o in v: walk_steps(o,cid)
for cid,d in db.items():
    for a in d.get('ab',[]):
        for k in a: abkeys[k].add(cid)
        walk_cond(a.get('if'),cid); walk_steps(a.get('do'),cid); walk_steps(a.get('cost'),cid)
def refd(k): return re.search(r"(\.|\[')"+re.escape(k)+r"\b|['\"]"+re.escape(k)+r"['\"]|\b"+re.escape(k)+r"\s*:",code) is not None
print('== 엔진이 처리하지 않는 op');
for op in sorted(ops):
    if not re.search(r"case '"+re.escape(op)+"'",code) and not refd(op): print(' ',op,len(ops[op]['op']),sorted(ops[op]['op'])[:5])
print('== op 파라미터 미참조')
for op in sorted(ops):
    for k,c in sorted(ops[op].items()):
        if k=='op' or k.startswith('to.'): continue
        if not refd(k): print(' ',op,k,len(c),sorted(c)[:5])
print('== 필터 키 미참조')
for k,c in sorted(filt.items()):
    if not refd(k): print(' ',k,len(c),sorted(c)[:5])
print('== 조건 키 미참조')
for k,c in sorted(conds.items()):
    if not refd(k): print(' ',k,len(c),sorted(c)[:5])
print('== ab 키 미참조')
for k,c in sorted(abkeys.items()):
    if not refd(k): print(' ',k,len(c),sorted(c)[:5])
json.dump({'filt':{k:sorted(v) for k,v in filt.items()},'conds':{k:sorted(v) for k,v in conds.items()},'ops':{o:{k:sorted(v) for k,v in m.items()} for o,m in ops.items()}},open('/tmp/keys.json','w'),ensure_ascii=False)
