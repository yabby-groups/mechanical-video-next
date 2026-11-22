# Apple Silicon Blender 后台渲染修复

## 复现和定位

Apple M3、macOS 27.3、Blender 5.3.0 ARM64（构建 02f0899d78e3）。修改前，受限执行器能启动 Blender 和初始化 bpy。默认场景和项目门把手场景进入渲染时都输出 no default Metal device available，并以 -6 / SIGABRT 退出。原始系统报告显示父进程为 Codex、宿主为 iTerm2，崩溃栈经过 WM_init_gpu_offscreen、GHOST_SystemCocoa::init 和 _RegisterApplication。同一台机器的登录会话存在 Aqua 和 GUI bootstrap 域，受限进程仍看不到默认 Metal 设备。使用获准的原生执行环境后，同一 Blender 二进制能渲染该项目场景。 [修改前记录](../output/render-repair-20261122/baseline/results.jsonl) · [原始崩溃报告](../output/render-repair-20261122/baseline/Blender-2026-11-22-080949.ips)

## 正式制作入口

从具有 Metal 访问能力的 macOS 登录会话运行现有 stage 或 produce 命令。在受限的 Codex 执行器中，正式 Eevee 或 Workbench 阶段需要获准的原生执行路径。启动器以绝对路径调用 Blender -b，过滤继承的 Python 和动态库注入变量，保留项目配置，记录调用者的 GUI 会话信息，在原会话内以独立进程组启动子进程。已有制作锁管理整个制作阶段，Blender 进程锁覆盖项目内各入口。默认单次超时为 3600 秒，可用 MVN_BLENDER_TIMEOUT_SECONDS 覆盖。

正式镜头以首个待渲染帧预检。macOS 上先在 Blender 进程内检查默认 Metal 设备，再使用原设引擎、相机、分辨率、灯光和采样渲染该帧。预检通过的帧直接进入帧序列。PNG 完成写入后原子发布，恢复时复用可解码的已存帧和已验证分块。完整缓存直接读取已有媒体。媒体缓存键与本次变更前兼容，源文件审计仍使用实际文件哈希。

每次运行保留 stdout、stderr、参数、Blender 版本、PID、耗时、退出码及信号。由系统生成且能匹配 PID 的原始崩溃报告会保留副本。生产日志索引和失败收据指向 output/render-diagnostics/。

| 分类 | 证据示例 |
| --- | --- |
| ENVIRONMENT_ERROR | 二进制无法执行、系统拒绝访问、动态库加载失败 |
| GRAPHICS_INIT_ERROR | 默认 Metal 设备不可用、离屏初始化错误或原生 Cocoa/Metal 初始化栈 |
| ENGINE_ERROR | Blender 报告引擎或设备不兼容，或渲染返回而没有保存目标帧 |
| SCENE_ERROR | .blend 加载失败或场景缺少渲染相机 |
| RESOURCE_ERROR | 内存或磁盘错误，或达到设定的执行时限 |
| UNKNOWN_CRASH | 日志尚不足以确定根因。收据的 process_crash 字段独立标记信号退出 |

遇到有证据支持的 Eevee 或 Cycles GPU 兼容问题，项目可在独立目录试渲一帧 Cycles CPU，并记录引擎、设备、材质、灯光、采样、输出尺寸和图像哈希。候选图标记 NEEDS_REVIEW，正式交付仍需按原流程验收。Metal 访问失败走执行环境分支。

## 独立诊断

    UV_CACHE_DIR=/private/tmp/mechanical-video-next-uv-cache uv run python -m mechanical_video_next.render_diagnostics --scene output/tasks/door-handle-return-20261121/cinematic/core-hd/scene.blend --frame 557 --timeout 45 --output output/blender-diagnostics-new

输出目录应为新目录。诊断串行执行各项测试，并在失败时继续收集其余结果。诊断实际调用 GPU 渲染入口以便复现。有失败或超时，诊断整体以 1 退出，各项的原始退出码保留在 JSON 中。

## 2026-11-22 本机验收

| 测试 | 受限 Codex 执行器 | 原生登录会话 |
| --- | --- | --- |
| 后台启动和 Python API | 两项均通过 | 两项均通过 |
| Workbench 单帧 | SIGABRT (-6) | 160×120，通过 |
| Eevee 单帧 | SIGABRT (-6) | 160×120，通过 |
| Cycles CPU 单帧 | 160×120，通过 | 160×120，通过 |
| Cycles Metal 单帧 | Blender 未发现可用设备，跳过 | 识别 10 核 M3 GPU，120 秒和 45 秒两次测试均超时 |
| 项目门把手 Eevee 第 557 帧 | SIGABRT (-6) | 1920×1080，3.484 秒，通过 |

- 修复后的正式入口在受限进程中记录 MTLCreateSystemDefaultDevice 返回 NULL，并在调用渲染操作前受控退出。独立诊断直接重现的 SIGABRT 记为进程级崩溃，完整系统报告随该次运行保留。 [正式入口预检](../output/render-repair-20261122/production-restricted/result.json) · [受限诊断](../output/render-repair-20261122/restricted-final/render_diagnostics.json) · [原生诊断](../output/render-repair-20261122/native-final/render_diagnostics.json)
- 第 557 帧与原后台命令生成的 RGB 像素逐个一致，源场景 SHA-256 校验通过。最终诊断中三次 SIGABRT 和一次 Metal 超时涉及的 Blender PID 均已退出，Metal 超时收据记录 -15 和回收成功。 [渲染帧](../output/render-repair-20261122/native-final/project-scene/frame.png) · [进程与像素对照](../output/render-repair-20261122/process-and-image-verification.json)
- 真实流水线在前两帧完成后注入编码故障。恢复时复用帧 1 和 2，从第 3 帧开始实渲，输出视频随后命中完整缓存。 [恢复与缓存收据](../output/render-repair-20261122/production-native/result.json) · [回归测试日志](../output/render-repair-20261122/regression-verified.log)

验收覆盖真实单帧与短片段的流水线回归。完整影片继续适用原有独立视听和机械动作审查。
