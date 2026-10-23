from pathlib import Path
root=Path(r'D:\元DGTF-多模并行架构')
src=root/'元DGTF-V1.30.4.py'
dst=root/'元DGTF-V2.0.0.py'
s=src.read_text(encoding='utf-8')
s=s.replace('元 DGTF · v1.30.4','元 DGTF · v2.0.0')
s=s.replace('__version__ = "1.30.4"','__version__ = "2.0.0"')
s=s.replace('v1.30.4','v2.0.0')
s=s.replace('元DGTF-V1.30.4.py','元DGTF-V2.0.0.py')
dst.write_text(s,encoding='utf-8')
print('V2 engine written',len(s))
# config header and takeover true
p=root/'dgtf_config.yaml'; c=p.read_text(encoding='utf-8')
c=c.replace('元DGTF · v1.30.4 配置文件','元DGTF · v2.0.0 配置文件')
c=c.replace('    takeover: false','    takeover: true')
p.write_text(c,encoding='utf-8')
print('config updated')
