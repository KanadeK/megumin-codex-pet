# 惠惠 Codex 宠物 + PetDiff

这是一个非官方、完全原创绘制素材的 Codex v2 动态宠物项目，同时包含可独立使用的
**PetDiff** 图集回归审查工具。它不是只展示图片的页面，也不是只复制文件的安装壳。

PetDiff 会检查 8×11、1536×2288 的 v2 图集合同，对 73 个必用格逐格提取透明面积、
包围盒、质心、轮廓与颜色指纹；同时允许 row 0 / col 6 的可选 neutral 姿态，并要求
其余 14 个保留格透明。它还会比较每个动画循环的运动节奏。结果可输出稳定 JSON 和
单文件 HTML，适合 PR 审查与 CI 留证。

v0.1.1 还会直接从最终 `pet/spritesheet.webp` 生成 9 个透明 GIF，检查尺寸、
帧数、时长和边界色。任何接近 `#00FF00` 的可见绿边都会使发布门禁失败。

## 最短验收路径

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\petdiff.exe validate pet
.\.venv\Scripts\petdiff.exe render-previews pet `
  --out-dir artwork\qa\previews `
  --qa-sheet artwork\qa\preview-background-check.png `
  --json-out artwork\qa\preview-audit.json
.\.venv\Scripts\petdiff.exe audit-previews artwork\qa\previews
.\.venv\Scripts\petdiff.exe check-lock pet pet\pet.lock.json `
  --policy examples\release-policy.json `
  --json-out build\petdiff-release.json `
  --html-out build\petdiff-release.html
.\.venv\Scripts\python.exe scripts\release_check.py --strict --json --json-out build\release-check.json
```

最后一个命令必须返回 0 且输出 `"ok": true`。若失败，不要跳过门禁；按
[REPAIR.md](REPAIR.md) 中对应错误码修复。

预览必须从最终宠物图集生成，禁止再使用
`artwork\hatch-run\frames` 下尚未完成去绿处理的中间帧。

## 安装、诊断与恢复

```powershell
petdiff package pet --out dist\megumin.codex-pet
petdiff verify-package dist\megumin.codex-pet
petdiff install dist\megumin.codex-pet
petdiff doctor megumin --lock pet\pet.lock.json
petdiff uninstall megumin
```

替换安装会把旧版本保留到 `${CODEX_HOME}\pets\.backups`。卸载只会移动到
`${CODEX_HOME}\pets\.trash`，不会永久删除。

## 权利说明

代码和文档采用 MIT。惠惠、《为美好的世界献上祝福！》相关人物设定、名称和底层
知识产权不属于本项目，也不会因为 MIT 而被重新授权。宠物素材必须是原创生成的同人
像素画，禁止复制官方插图、动画帧、商标、台词或音频。公开传播或商用前请自行获得
必要许可；完整说明见 [RIGHTS_AND_ASSETS.md](../RIGHTS_AND_ASSETS.md)。
