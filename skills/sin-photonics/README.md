# SiN photonics — 自包含 Skill 2.0

独立计算300 nm SiN圆环—直总线耦合，以及直段/圆弧路线的相干保留模式传输。本目录就是完整的安装与Git发布单元；无需下载研究工作台、另一个Skill或历史测试包。

## 安装

发布后将独立仓库克隆到本机的Codex用户Skill目录。以下PowerShell命令中的`<仓库URL>`应替换为实际发布地址；当前本地开发不等于已发布。

```powershell
git clone <仓库URL> "$env:USERPROFILE\.agents\skills\sin-photonics"
Set-Location "$env:USERPROFILE\.agents\skills\sin-photonics"
python -m pip install -r requirements.txt
python scripts/run.py doctor
```

也可以先克隆到任意位置，再将**整个目录**安装到Skill目录，或让Codex的Skill安装器安装该仓库。该目录包含所需全部运行代码；只复制`SKILL.md`是不完整的安装。更新直接在克隆目录运行`git pull`，依赖变化时重跑requirements安装。

运行环境：Python≥3.11，NumPy≥2、SciPy≥1.14、jsonschema≥4.20。真正的新FEM求解需要Windows上的COMSOL6.1及相应电磁模式求解许可；COMSOL本体和许可证不随Skill分发。当前原生求解入口仅验证Windows。`doctor`检查依赖、内置文件与绘图依赖哈希；许可证是否可用由真实求解确认。

```powershell
python scripts/run.py doctor --comsol-bin "D:/COMSOL61/Multiphysics/bin/win64" --require-comsol
python scripts/run.py ring-bus --config examples/ring-scan-small.json --plan
python scripts/run.py ring-bus --config examples/ring-reference.json --output <新的结果目录> --comsol-bin <本机bin/win64目录>
python scripts/run.py bends --config examples/bend-single.json --output <新的结果目录> --comsol-bin <本机bin/win64目录>
python scripts/run.py guide --output <允许的输出目录>/model-and-equations.html
```

命令可以从任意工作目录运行，只需给出`run.py`和配置文件的正确路径。无需`PYTHONPATH`、`SIN_PHOTONICS_HOME`或`SIN_PLOTTING_ROOT`。工具可通过`COMSOL_BIN`或`--comsol-bin`找到本机COMSOL。输出目录必须新建；在WorkBench开发测试时只写允许的测试目录。

在Codex中可用`$sin-photonics`请求计算。规划扫描及生成模型说明不需要COMSOL；只有调用求解器才需要它。完整物理含义、窗口收敛、缺失TE1处理和原生解映射见[操作说明](references/operation.md)及[物理边界](references/physics-boundaries.md)。

## 目录与源码

```text
sin-photonics/
  SKILL.md                       # 助手工作流程
  requirements.txt               # Python依赖
  examples/                      # 小型配置示例
  references/                    # 物理和操作说明
  scripts/run.py                 # 唯一推荐运行入口
  scripts/toolkit/sinphotonics/   # 唯一维护的模型与算法源码
  scripts/toolkit/docs/          # 模型说明HTML源模板
  scripts/toolkit/scripts/       # 模型说明、显式实验对照和模板导出
  scripts/plotting-runtime/      # 固定版本绘图依赖与来源哈希
  tests/                         # 轻量测试和显式数据回归入口
```

SiN/SiO₂全部材料系数位于`scripts/toolkit/sinphotonics/materials.json`，只内置`reference300-v1`。COMSOL完整建模程序位于同目录的`native/NativeModes.java`，运行时建立几何、材料、网格、PML、研究和参数扫描，并生成带解MPH。Git无需携带MPH、原始模场、缓存或大型测试输出。

模型采用独立截面模式及有限前向模式近似；数值守恒、双域一致和积分窗口收敛不等于全器件全波或实验验证。缺失或失败通道会明确保留诊断状态。厚度扰动沿用300 nm工艺的材料参数，不引入另一套材料拟合。

## 验证与维护

```powershell
python -m unittest discover -s tests -p "test_*.py"
python scripts/vendor_plotting.py
```

以上检查不需要科学数据或COMSOL。真实模式回归用`tests/verify_v11.py`或`tests/verify_reference.py`显式传入数据；这些可选大数据不会随安装下载。`tests/verify_standalone.py`用于隔离安装验收；其参数要求调用者明确输出、输入数据和可选COMSOL路径。

光子学源码只维护此目录中的一份。`scripts/plotting-runtime/`是可重复生成的依赖快照：先在科学绘图源码项目修复并提交，再用`python scripts/vendor_plotting.py --repository <源码仓库> --revision <commit>`更新。快照文件禁止单独手改，版本和SHA256保存在`provenance.json`。快照采用固定LF字节，Git克隆后哈希不随Windows换行设置变化。

在Workbench中发布独立分支可用`git subtree split --prefix=skills/sin-photonics -b <新的发布分支>`；该分支根目录就是本目录，可独立clone或推送至专门仓库。发布前须对实际克隆内容验收。推送GitHub仍须用户明确授权。
