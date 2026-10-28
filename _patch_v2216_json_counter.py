import py_compile
from pathlib import Path
P = Path("dgtf_local_llm/service.py")
text = P.read_bytes().decode("utf-8-sig")
def rep(old, new):
    global text
    c = text.count(old)
    assert c == 1, "锚点命中 %d 次" % c
    text = text.replace(old, new)

rep('                  "graph_capture_keys": [],',
    '                  "graph_capture_keys": [],\n'
    '                  "json_forced_generations": 0,')

rep('                if _pen_on:\n'
    '                    self.stats["graph_rep_pen_generations"] = int(\n'
    '                        self.stats.get("graph_rep_pen_generations", 0)) + 1',
    '                if _pen_on:\n'
    '                    self.stats["graph_rep_pen_generations"] = int(\n'
    '                        self.stats.get("graph_rep_pen_generations", 0)) + 1\n'
    '                if json_mode:\n'
    '                    self.stats["json_forced_generations"] = int(\n'
    '                        self.stats.get("json_forced_generations", 0)) + 1')

P.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
py_compile.compile(str(P), doraise=True)
print("OK json_forced_generations counter")
