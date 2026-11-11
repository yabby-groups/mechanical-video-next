# Mechanical Video Next

当前视觉参考已明确为**打印机系列 EP03**：机械主体全画面、灰色空间、金属材质、柔和阴影、斜视与克制的镜头推进，少量标注及底部字幕。`config/planetary-01.json` / `planetary-02.json` 已采用该预设，配音保持 Neil。旧左右分栏配置保留为 `*-panel.json`，既有成片保留。`config/planetary-fullframe-style.json` 是只改版式的中间版本；实际材质灯光预览使用 `config/planetary-printer-ep03-style.json`、现有 EEVEE 渲染器及 `blender/studio_style.py` 小型预设，不复制旧架构。参考风格不等于科学或完整视听验收。

```sh
python3 scripts/style_preview.py config/planetary-printer-ep03-style.json --phase keys
python3 scripts/style_preview.py config/planetary-printer-ep03-style.json --phase preview
python3 scripts/produce.py config/planetary-printer-ep03-style.json --phase preview
```

本地、素材优先的机械科普生产项目。三个 Skills 保留；Codex 主会话作为 Producer，五个窄职责子代理负责研究、资产、动画、剪辑、独立 QA。Blender/EAS 制作镜头，Remotion 合成，FFmpeg 检测。视频号统一默认旁白为 Qwen3-TTS / Neil，与卷尺同款。首期是有独立零件的简化行星齿轮教学装配，不是工业 CAD 或接触仿真。

## 多 Agent 入口

项目级 `.codex/config.toml` 和 `.codex/agents/*.toml` 使用当前官方独立角色文件格式，最多三个子代理，无第二个 Producer，不修改全局配置。已在 Codex CLI 0.167.0 严格配置模式验证五个角色加载；官方依据：[Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)。配置不会热加载进已存在的会话，本次协作使用当前会话的原生 collaboration 子代理工具并显式传入角色职责。

```sh
# 在当前 Codex 会话中创建制作任务，由该会话继续派发真实子代理
python3 -m mechanical_video_next produce --topic "行星齿轮为什么能减速" --duration 36 --config config/planetary-01.json
# 从终端启动一个新的 Codex Producer，原生子代理由 Codex 调用
python3 -m mechanical_video_next produce --topic "行星齿轮为什么能减速" --duration 36 --config config/planetary-01.json --codex
```

默认命令只创建 `output/tasks/<id>/task.json` 和 `producer-prompt.md`，不会凭 Python 自动拥有智能调度。`--codex` 调用真实 `codex exec --json`，保存原生日志 `codex.jsonl`；需要已登录、受信任的项目和可用的 Codex 服务。已在 Codex 内工作时不要嵌套启动 Producer。原有 `scripts/produce.py` 为单 Agent 回退。

`--voice` 是给 Producer 的明确音色要求，不能绕过现有语音批准与试听流程；默认保留已选 Neil。只有现有行星教学装配已接入固定镜头；任意选题、真实电钻、2.5D 路线尚不能保证自动制作。不匹配的选题必须由 Research/Asset 阻断，不把行星示意替代真实电钻结构。45 秒是可请求目标，首条回归基线为现有 36 秒；不能为凑时长加速声音。

Research 与 Asset 并行，Animation 等待其合格交接，Editor 等待镜头时间轴，QA 独立读取实际媒体。每个 JSON 经 `handoff` 保存独立版本、所有权和依赖哈希，变化后旧依赖失效。状态前进用 `advance`，不是根据退出码直接 COMPLETED。

```sh
python3 -m mechanical_video_next handoff output/tasks/<id> --role Research --name research --input research.json
python3 -m mechanical_video_next handoff output/tasks/<id> --role Research --name script --input script.json --depends research
python3 -m mechanical_video_next advance output/tasks/<id> RESEARCHING
python3 -m mechanical_video_next stage output/tasks/<id> keys --config config/planetary-01.json
python3 -m mechanical_video_next status output/tasks/<id>
```

上述 stage 需要先登记合格资产并达到 ASSET_READY，完整依赖与命令见 CLI `--help` 和 AGENTS.md。门禁核对实际模型/媒体哈希、关键帧、技术报告及独立 QA；QA 的 UNKNOWN 阻止进入 EDITING/COMPLETED。`stage ... final --workprint` 只允许在 PREVIEW_CHECKING 且 QA 无 FAIL 时生成明确未验收工作样片，不推进状态。单纯 FFmpeg 扫描、截图抽样不能冒充连续观看、听审或原理完整验收。

全局 `work/production.lock` 串行制作与清理；重任务不随 Agent 数量并行。stage 前自动清理超过七天、已完成且未锁定/受保护/被任务引用的可再生缓存，保留 assets、output 和失败证据。直接运行原始单 Agent 脚本时不要并发启动重任务。

## 局部修复与验收

生产协议支持有证据的修复登记，每问题至多两策略、每策略两轮，无改善立即停止。确定性自动修复适配器当前只覆盖已绑定配置哈希和 cue 的字幕缺陷，其他类型由 Producer 选择现成模板、资产或逐句语音配置后重新交接；没有声称具备任意几何/相机/听感自动判断器。

```sh
python3 -m mechanical_video_next.repairs output/tasks/<id> --config <video.json> --issue SUBTITLE-1 --shot s1 --cue 0 --text "修正字幕"
python3 scripts/acceptance.py --run --scenario 1 2 3 4 5 7
python3 -m unittest discover -s tests -v
```

修复适配器复用已有最终镜头，只重新合成，要求实际 QA 缺陷、精确媒体/配置哈希及 Editor 责任。修复结果仍需新的独立 QA，不直接关闭缺陷或标记成片合格。第六场景需要真实 QA 发现明确标记的受控故障、执行适配器和独立复验，回归脚本不会伪造该过程。第三场景仅修改旁白文本，复用已缓存 Neil 语句并刻意固定字幕作为隔离实验；该测试文件不能当可发布内容。

本次本地证据位于 `output/multi-agent-pilot/`：final.mp4、captions.srt、timeline.json、独立 QA、研究/资产/动画交接、失败证据、acceptance.json。`output/tasks/pilot-20261111/` 保存状态门禁、版本化交接和原生线程协作记录。媒体和本次任务数据未纳入 Git，仍保留在本机。成本统计区分生产工具耗时、Agent 耗时和工程修改；原生接口不暴露的 Token/人工介入计量填 null，不编造零成本。

本次另从本机原生会话 JSONL 提取了真实线程 UUID、完成时间与 Token 快照，见 `native-collaboration.json`；只导出元数据，不复制会话文本或密钥。它包含工程和制作多个回合，不能作为单条视频价格或节省比例。`scripts/codex_usage.py` 可对指定日期目录和 root thread 再提取；本地日志格式不是稳定公共 API，不存在时仍填 null。首轮开发使用了完整上下文继承，后续生产协议改为工具支持时使用新子代理上下文，仅传路径与交接哈希；尚无可比的 Token 降本结论。

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

当前默认输出为横屏 1920×1080/30fps/H.264/AAC，fullframe 3D 使用同一画幅，预览为 960×540。打印机 EP03 视觉预设使用现成 EEVEE 渲染器、PBR 材质及柔和区域灯；未启用 Cycles。历史 panel 配置保留 Workbench 和原先的独立机械面板。字幕时轴来自每句 TTS 音频实际起止，不是音素强制对齐。

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

原始单 Agent 脚本异常即停，不自动重试。多 Agent 入口仅对有证据的明确缺陷作有限局部修复，策略与次数见上文。本期历史上发生一次媒体修复：低清 625 高度无法编码 H.264，给编码增加单像素 padding 后直接复用原帧通过。环境启动和 npm 缓存权限问题另计，不冒充零工程干预。

## 上游与许可

- EAS 1.14.0：GPL-2.0-or-later，最低 Blender 4.2；固定提交与上游源见 `blender/vendor/SOURCES.json`。原样保留插件及许可证；其真实后台测试通过 335 项。
- Blender 官方 gear generator：GPL-2.0-or-later，固定提交和作者头部已保留，简化齿形边界如上。
- Remotion 4.0.542：自定义许可证，个人、至多 3 员工的营利组织、非营利组织和非商业评估可免费；更大营利组织需要公司许可。全文见 `remotion/UPSTREAM-LICENSE.md`。本项目是本地可行性评估，未来商业使用需核实组织资格。
- Manim Community 0.22.1：MIT；仅查验上游，未安装，也没有进入制作链。
- FFmpeg 当前构建启用 GPL/version3 与 libx264，分发二进制需按其许可处理。
- macOS 系统语音仅已证明本地合成成功，声音再分发条款未做法律核验。

本项目新 Python/TypeScript 代码使用 GPL-3.0-or-later；新教学场景、分镜和解说使用 CC0-1.0。上游代码、系统语音、字体和依赖仍受各自许可约束。没有执行上传、保存平台草稿或发布。

## 横屏默认输出

`config/planetary-01.json` 和 `planetary-02.json` 默认 1920×1080、30 fps、H.264/AAC，使用已选定的 Neil 普通话旁白。视觉参照打印机系列 EP03，采用全画面机械主体、灰色空间、金属材质、柔和阴影及底部逐句字幕。Blender 按完整横屏画幅取景，渲染尺寸与视觉预设源码进入镜头缓存键。当前文件使用 `-fullframe` ID；旧 panel 配置、横屏及竖屏 MP4 保留。

```sh
/usr/bin/python3 scripts/produce.py config/planetary-01.json --phase keys
/usr/bin/python3 scripts/produce.py config/planetary-01.json --phase preview --env-file /path/to/local.env
/usr/bin/python3 scripts/produce.py config/planetary-01.json --phase final --env-file /path/to/local.env
```

支持保留 1080×1920 配置供历史版式复用；改变配音或字幕不会改变 3D 缓存键。横屏也必须先验证关键帧、低清全片，再输出正式成片。
