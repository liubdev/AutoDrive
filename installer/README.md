# AutoDrive MSI 安装器

本目录使用 WiX v7 生成带品牌化引导界面的 MSI。WiX v7 继续兼容本项目使用的
WiX v4 XML 命名空间；`setup.py` 负责生成
cx_Freeze 程序目录，`build.ps1` 负责将程序目录封装为最终安装包。

## 构建

先安装 WiX Toolset v7，并确保 `wix.exe` 已加入 PATH，然后在项目根目录执行：

```powershell
PowerShell -ExecutionPolicy Bypass -File .\installer\build.ps1
```

如果已经存在最新的 `build\exe.*`，可以跳过冻结步骤：

```powershell
PowerShell -ExecutionPolicy Bypass -File .\installer\build.ps1 -SkipFreeze
```

生成文件：

```text
dist\AutoDrive-Setup.msi
```

修改安装引导文案：`AutoDrive.wxl`

文案字段已同步整理在 `texts.json`，后续接入数据库时，可将数据库记录映射为
相同的 JSON 字段，再由构建脚本生成 WiX 本地化文件。

修改安装流程、快捷方式和安装目录：`AutoDrive.wxs`

修改欢迎页视觉：`dialog.bmp`

当前安装器采用 WiX v7 的 `WixUI_InstallDir` 标准向导，并通过欢迎页背景和
程序图标实现 RunchTech 品牌化展示。顶部横幅使用 WiX 默认样式，避免图片与
标题文字重叠。

安装完成页使用独立的纯色布局，提供默认勾选的“添加快捷方式到桌面”和
“启动 AutoDrive”。点击完成后才执行勾选的操作；取消勾选不会新建桌面快捷方式。
桌面快捷方式属于当前用户，使用安装目录的 icon.ico；卸载清理当前卸载用户的
对应快捷方式，不删除指向其他程序的同名快捷方式。其他 Windows 用户自行创建的
快捷方式不在清理范围内。静默安装没有完成页，不创建桌面快捷方式、不启动应用。
安装、修复、卸载分别显示对应完成标题。修复使用 MSI 原生维护操作，不是清空
个人配置后重装；卸载保留用户配置和诊断报告。当前 MSI 使用 per-machine
安装模式，双击时可能出现一次普通权限到管理员权限的界面切换；如果需要彻底
消除这类闪烁，应进一步增加 WiX Burn 引导器。

当前版本为 1.0.2，ProductCode 在该版本内固定，重复运行同一 MSI 可进入维护模式。
发布更高版本时同时更新 setup.py 和 AutoDrive.wxs 中的版本，并为新版本生成新的
ProductCode，保持 UpgradeCode 不变。不要用同一版本号发布内容不同的正式安装包。

发布验收应在 Windows Sandbox 或测试机完成：全选安装、取消两个选项安装、
删除程序文件后修复、卸载、旧版本升级到 1.0.2；每项检查快捷方式、文件和完成页。

项目脚本已按用途整理到 `scripts/tests`、`scripts/probes` 和 `scripts/tools`。
根目录下的 `scripts/run_dts.py`、`scripts/run_dts_last_step.py`、
`scripts/build_knowledge.py` 仍保留兼容入口，旧命令无需修改。
