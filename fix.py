# scan_n.py
from pathlib import Path

p = Path(r"C:\Users\18432\Desktop\元DGTF-多模并行架构\元DGTF-V1.21.50.py")
src = p.read_text(encoding="utf-8")
lines = src.splitlines()

print(f"文件总行数: {len(lines)}")
print(f"含字面 '/n' 的行数: {sum(1 for l in lines if '/n' in l)}")
print(f"含字面 '\\\\n' 的行数: {sum(1 for l in lines if '\\\\n' in l)}")
print()

# 列出所有 /n 出现的位置
for i, line in enumerate(lines, 1):
    if "/n" in line:
        print(f"行 {i}: {line[:140]}")