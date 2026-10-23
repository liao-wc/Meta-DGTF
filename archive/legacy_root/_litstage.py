import ast
s=open('元DGTF-V1.30.0.py',encoding='utf-8').read()
t=ast.parse(s)
for n in ast.walk(t):
    if isinstance(n,ast.Call):
        for kw in n.keywords:
            if kw.arg=='stage' and isinstance(kw.value,ast.Constant) and isinstance(kw.value.value,str):
                print(n.lineno,getattr(n.func,'id',getattr(n.func,'attr','?')),kw.value.value)
