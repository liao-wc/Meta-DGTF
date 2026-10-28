提案目标：修复 precheck G5 事实题质量门未通过：我国义务教育法规定小学入学年龄。
证据：python scripts/precheck_quality.py 输出 G5 quality：uncovered 我国义务教育法规定小学入学年龄；answer_ready=False（事实证据未覆盖题面/无官方依据）。
影响：这是真实质量缺口；不能把 fact 改成 reasoning 或直接豁免来通过门禁。
步骤：
1. 定位对应 packed/产物，核对题面、证据源和 uncovered 原因；
2. 补官方源（义务教育法/教育部）或修正题面主体/年代，必要时追加 1 次 web-on 真跑；
3. 只修改确定性证据/规则，不降低质量门；
4. 重跑 precheck_quality / fast_gate / selftest / V2 tests；
5. 记录前后 answer_ready、verified、uncovered 变化。
验证：python scripts/precheck_quality.py；python fast_gate.py；python dgtf_app/selftest.py；python scripts/run_v2_tests.py。
风险：追加真跑消耗预算；改题面可能改变答案口径；不得用分类掩盖证据缺口。
需人工决策：是否允许补证并追加真跑、预算上限及是否接受题面修订。
