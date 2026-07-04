#!/usr/bin/env python3
from math import isclose

def tiou(a0,a1,b0,b1):
    inter=max(0,min(a1,b1)-max(a0,b0))
    union=max(a1,b1)-min(a0,b0)
    return inter/union if union else 0.0

def event_recall(cands, events, th=.3):
    hits=0
    for ev in events:
        if any(tiou(c[0],c[1],ev[0],ev[1])>=th for c in cands):
            hits+=1
    return hits/len(events)

def duplicate_rate(cands, events, th=.3):
    hits=[]
    for c in cands:
        matched=[i for i,e in enumerate(events) if tiou(c[0],c[1],e[0],e[1])>=th]
        hits.extend(matched[:1])
    return (len(hits)-len(set(hits)))/len(cands) if cands else 0.0

def cils(cands, tau):
    sel=[]; tp=tot=0
    for c in sorted(cands, key=lambda x: x["p"]*x["value"], reverse=True):
        ntp=tp+c["p"]*c["value"]; ntot=tot+c["value"]
        if ntp/ntot >= tau:
            sel.append(c); tp,tot=ntp,ntot
    return sel, (tp/tot if tot else 0)

assert isclose(tiou(10,20,10,20),1.0)
assert isclose(tiou(8,22,10,20),10/14)
assert isclose(tiou(0,5,10,20),0.0)
assert event_recall([(10,20),(8,22),(0,5)], [(10,20)]) == 1.0
assert event_recall([(9,19),(10,20),(40,50)], [(10,20),(40,50)]) == 1.0
assert duplicate_rate([(9,19),(10,20),(40,50)], [(10,20),(40,50)]) > 0
toy=[{"id":"h","p":.95,"value":1},{"id":"m","p":.55,"value":1},{"id":"l","p":.2,"value":1}]
lo,_=cils(toy,.5); hi,_=cils(toy,.9)
assert len(lo) > len(hi)
assert [x["id"] for x in hi] == ["h"]
print("PASS synthetic metric and selector cases")
