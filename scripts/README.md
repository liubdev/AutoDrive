# 脚本目录

```text
scripts/tests/   自动化测试和 GUI 冒烟测试
scripts/probes/  不启动真实 DTS 的逻辑探针
scripts/tools/   DTS 运行器和知识库构建工具
```

根目录下的三个 Python 文件是兼容入口，旧命令仍然有效：

```powershell
python scripts/run_dts.py
python scripts/run_dts_last_step.py
python scripts/build_knowledge.py
```

新路径示例：

```powershell
python scripts/tools/run_dts.py
python scripts/tests/test_ai.py
```
