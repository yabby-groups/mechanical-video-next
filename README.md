# Mechanical Video Next

本地、素材优先的最小机械科普生产项目。只有三个 Skills；Blender/EAS 制作镜头，Remotion 合成，FFmpeg 检测。首期成片使用 macOS `say` 普通话；视频号统一默认旁白为 Qwen3-TTS / Neil，与卷尺同款。首期是有独立零件的简化行星齿轮教学装配，不是工业 CAD 或接触仿真。

## 运行

已验证设备：Apple M3 / 16 GB / macOS 27.3；Blender 5.2.3 LTS，FFmpeg 9.0.1，Python 3.9.6，Node 26.11.1。`BLENDER` 环境变量可覆盖默认应用路径。macOS 沙箱可能需要允许 Blender 后台应用启动；普通沙箱曾在进入 Python 前崩溃，完整本机运行通过。

```sh
npm ci --prefix remotion --cache work/npm-cache --no-audit --no-fund
python3 scripts/environment.py
python3 scripts/produce.py config/planetary-01.json --phase keys
python3 scripts/produce.py config/planetary-01.json --phase preview
python3 scripts/produce.py config/planetary-01.json --phase final
python3 scripts/produce.py config/planetary-02.json --phase all
python3 -m unittest discover -s tests -v
npm run --prefix remotion typecheck
```

依赖已锁定在 package-lock.json。使用已安装 Chrome，不额外下载 Chromium。已交付的 Tingting 成片不需要 API 密钥；Neil 默认旁白通过现有兼容语音网关调用，需要 API 密钥，但不下载本地 TTS 模型。macOS say 分支需有可实际合成的 Tingting voice；仅列出 voice 不代表音频可生成。Neil 使用标准 HTTPS/Python/FFmpeg，但目前只在这台 Mac 做过真实运行验证。

## 统一中文旁白：卷尺同款 Neil（已启用默认）

`config/narration-default.json` 已按用户“和卷尺的音色一致”“设置为默认的音色”的明确指令启用 `config/narration-neil.json`：模型 `qwen3-tts-flash`，音色 `Neil`（阿闻），1.0 倍原速。实际核对了旧卷尺 EVERYDAY_EP03 的 speech-execution.json 和 timeline 记录，音色为 Neil、没有后期加速；只复用音色参数，没有迁移旧项目架构。

Neil 的系统音色偏清晰、沉稳的男声，延续纪录片式自然表达的目标。当前接口没有已验证的原生数值语速、风格或重音指令，使用分句、标点和叙述措辞引导表达，不把不支持的参数当成已生效。目标 1.0 时不使用 atempo；明确调速时只允许 0.95–1.05，并重测字幕时轴，禁止为卡镜头自动加速。

```sh
python3 scripts/narration.py audition --env-file /path/to/existing.env
# 完成缓存后，无密钥也可复用当前默认音色的试听
python3 scripts/narration.py audition
python3 scripts/produce.py config/planetary-01.json --phase all --env-file /path/to/existing.env
```

新试听位于 `output/narration-audition/neil-documentary-audition-v1/`，保留完整 WAV、三个镜头 WAV、SRT 和实测数据。Kai 文件与 `config/narration-audition-kai.json` 只保留为历史对比，不是默认音色。既有 MP4 不重配，新制作由 profile 选择 Neil。

原始、逐句和逐镜头 WAV 缓存于 `assets/audio/narration/`，不会被 work 清理删除。原始请求按模型、音色、文本、端点哈希，处理音频按 profile/代码哈希；换音色不会误用旧声音，修改字幕或处理代码不重复提交原始合成。请求提交写 submitted.json，不确定完成状态不得自动重复付费请求。

FFmpeg 使用双遍 loudnorm，目标 -16 LUFS / -1.5 dBTP，验收容差 ±1 LU、峰值 +0.2 dB。短句第一策略允许一次至多 2 dB 的峰值受限修正；仍不合格时仅一次 2:1 峰值预压缩后按实测响度静态增益与限制器的第二策略，再失败就停。FFmpeg 静音边界保留开头 60 ms、结尾 100 ms 余量，结合处理后 WAV 的 FFprobe 实测时长与混音偏移作逐句字幕，不声称字级或音素强制对齐。超时写 overrun.json 并停止。

批准记录绑定不可变的精确音频与 profile 哈希。当前批准依据是 **explicit_reference_voice_selection**（用户明确选择卷尺同款作为默认），没有声称用户已听审新文案。未来用户明确选择某个既有参考音色并要求设为默认，可用 `activate --receipt <audition.json> --confirmed-selection`；确实试听确认后则用 --confirmed-listened。未经授权改变 profile 不可沿用旧批准。只对 `channel: 视频号` 自动套用默认，显式 narration_profile 也必须指向已批准的 profile。

密钥仅从环境变量、被忽略的 .env.local 或 --env-file 读取，.env.example 只有空值模板。

## 配置与缓存

Git 保存源码、配置、资产来源与部件清单。生成的 Blend、音频缓存和 output 交付留在本地；唯一纳入 Git 的媒体是默认 Neil 音色批准记录绑定的试听 WAV，与不可变批准 JSON 一起保留，以便新检出核验默认音色。新检出尚未生成的 MP4 和运动证据测试会跳过，需按上述制作命令重新生成。

每条视频只编辑一个 `config/planetary-0*.json`。其中指定资产 ID、固定模板、拆解距离、镜头长度、顺序、屏幕说明、解说、配音和编码规格；资产清单与运动参数保存在该 ID 的 `config/assembly.json`。六段分镜复用五个模板；两个原理段引用同一个运动短片。

`components`、`motion_template`、`explosion_sequence` 显式声明本期已验证的部件和轴向拆解预设；当前只接受这套预设序列，不能自动规划任意零件的安全拆解路径。分镜顺序与距离/时间可以改；`subtitles` 可单独修订文字，不重生成配音或 3D。字幕条数需与逐句配音一致。

`overall / explode / detail / motion / assemble` 分别实现整体、逐层拆解、特写、原理、回装。EAS 的组移动、保存位置和回装直接调用成熟插件。`exploded` 也支持静态爆炸图。自动取景覆盖采样姿态，随后对全部帧进行投影边界检查。色彩固定：太阳轮橙、行星轮蓝、齿圈银、行星架绿。

缓存层分别为装配、每镜头的关键帧/低清/正式、每段音频、最终合成；读取时核对 SHA-256。修改 narration 只影响音频与合成；修改屏幕说明、字幕样式只影响合成；修改单镜头仅影响对应镜头及合成。整体场景源或资产参数变化会保守地失效相关模型和镜头缓存。源码算法变化仍需更新相应缓存版本，不支持任意热修改后猜测等价。

最终输出是 1080×1920/30fps/H.264/AAC MP4；3D 画面原生 1080×1250，放入带标题、说明和字幕的竖版画布。预览为 540×960。使用 Workbench 做快速教学渲染，未启用 Cycles 光线追踪。字幕时轴来自每句 TTS 音频实际起止，不是音素强制对齐。

## 资产与科学边界

`assets/assemblies/planetary-teaching-v1/` 保留已验证的模型、部件清单和来源；模型一次生成后缓存复用。几何使用 Blender 官方 `add_mesh_extra_objects` 的现有齿轮生成器及基本图元，不开发 CAD 内核。没有把单个整网格冒充装配体。齿数 18/18/54，三个等距行星，满足 `Zr=Zs+2Zp` 与 `(Zs+Zr)/3` 为整数。

固定齿圈的 Willis 关系为 `Zs(ωs−ωc)+Zr(ωr−ωc)=0`；`ωr=0`，因此 `ωc=ωs/4`。行星自转满足外啮合相对速度式，中心随行星架公转。`scripts/check_motion.py` 独立读取 241 帧实际 Blender 关键帧检查轨迹和速度约束。8 秒运动素材中太阳轮转 2 圈、行星架转半圈；片中“四圈一圈”是比例解释，未声称镜头拍到了四整圈。

齿廓来自简化生成器，未验证渐开线啮合、接触、强度、效率、碰撞和真实拆装路径；外壳是教学盖板。视频全程标注“原理示意”。投影检查不验证遮挡，音轨扫描不判断发音自然度。完整独立视听和科学审阅仍开放，状态只能是 `TECHNICAL_PASS_UNACCEPTED_TEACHING_DEMO`。

本地 GLB 或已打包 Blend 可登记、检查独立网格与来源：

```sh
python3 scripts/import_asset.py model.glb --origin https://example.org/model --license CC-BY-4.0 --version v1
```

单网格、未知许可证会拒绝进入素材库；导入不证明部件语义或授权声明真实。新资产需部件映射与运动资料，当前全片模板只集成这一套行星装配。STEP 需要外部 FreeCAD 转换，本项目没有安装或实现该转换。

## 磁盘、生命周期与失败

work 预算 2 GiB，生成前保守估算未压缩帧上界；每 0.5 秒采样占用，另要求至少 3 GiB 空闲。临时 PNG 编码并完整解码后仅删除对应序列，关键帧保留。峰值为采样实测值，可能漏掉小于采样间隔的瞬时峰值。node_modules、Blender 应用和正式交付不计入 work 峰值，报告另列目录大小。

缓存默认保存 7 天，清理先 dry run，必须显式 `--apply` 才删除已完成且命名合法的缓存条目；资产与成片永远不在删除范围。不自动清除未知临时目录或失败证据；这些需明确检查后处理。

```sh
python3 scripts/clean.py --older-hours 168
python3 scripts/clean.py --older-hours 168 --apply
```

不存在自动返工循环：异常即停。明确问题的修复只允许两种策略、各至多两次且有量化改善。本期发生一次媒体修复：低清 625 高度无法编码 H.264，给编码增加单像素 padding 后直接复用原帧通过。环境启动和 npm 缓存权限问题另计，不冒充零工程干预。

## 上游与许可

- EAS 1.14.0：GPL-2.0-or-later，最低 Blender 4.2；固定提交与上游源见 `blender/vendor/SOURCES.json`。原样保留插件及许可证；其真实后台测试通过 335 项。
- Blender 官方 gear generator：GPL-2.0-or-later，固定提交和作者头部已保留，简化齿形边界如上。
- Remotion 4.0.542：自定义许可证，个人、至多 3 员工的营利组织、非营利组织和非商业评估可免费；更大营利组织需要公司许可。全文见 `remotion/UPSTREAM-LICENSE.md`。本项目是本地可行性评估，未来商业使用需核实组织资格。
- Manim Community 0.22.1：MIT；仅查验上游，未安装，也没有进入制作链。
- FFmpeg 当前构建启用 GPL/version3 与 libx264，分发二进制需按其许可处理。
- macOS 系统语音仅已证明本地合成成功，声音再分发条款未做法律核验。

本项目新 Python/TypeScript 代码使用 GPL-3.0-or-later；新教学场景、分镜和解说使用 CC0-1.0。上游代码、系统语音、字体和依赖仍受各自许可约束。没有执行上传、保存平台草稿或发布。

## 横屏默认输出

`config/planetary-01.json` 和 `planetary-02.json` 默认 1920×1080、30 fps、H.264/AAC，使用已选定的 Neil 普通话旁白。左侧机械镜头、右侧说明、底部逐句字幕；Blender 按横屏面板重新取景，渲染尺寸进入镜头缓存键。现有竖屏 MP4 保留，横屏文件使用 `-landscape` ID。

```sh
/usr/bin/python3 scripts/produce.py config/planetary-01.json --phase keys
/usr/bin/python3 scripts/produce.py config/planetary-01.json --phase preview --env-file /path/to/local.env
/usr/bin/python3 scripts/produce.py config/planetary-01.json --phase final --env-file /path/to/local.env
```

支持保留 1080×1920 配置供历史版式复用；改变配音或字幕不会改变 3D 缓存键。横屏也必须先验证关键帧、低清全片，再输出正式成片。
