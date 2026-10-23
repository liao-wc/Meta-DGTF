import ast,json
s=ast.parse(open('元DGTF-V1.30.0.py',encoding='utf-8').read())
def syms(t):
 out=set()
 for n in ast.walk(t):
  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)): out.add(n.name)
 return out
b=syms(ast.parse(open('_baseline_v12177.py',encoding='utf-8').read())) if __import__('os').path.exists('_baseline_v12177.py') else set()
cur=syms(s); reg=set(json.load(open('_v122_ast_registry.json',encoding='utf-8')).get('registry') or {})
print('ADDED',len(cur-b),'UNREG',sorted(cur-b-reg))
