# 原风格锁定与手机文字专项结果

仅改后期文字、缓存边界和QA工具；没有启动新制作、CAD、Blender或TTS，没有覆盖历史成片。本次交付是通用实现和真实诊断，**不是整条历史视频的正式验收**。

## 修改文件

| 文件 | 内容 |
|---|---|
| `assets/style-reference/approved-original.png` | 用户真实截图，SHA256 `49e2b782422c04994cbd79c56e1e3900416e6a117ff8145c8fc32e7453a572ed` |
| `assets/style-reference/style-lock.json` | 截图来源、允许修改范围、背景/材质/灯光/相机/运动参数与哈希锁 |
| `assets/style-reference/approved-renderer.tsx` | 修改前真实Git合成源码，用于回归，不是仿制参考图 |
| `config/text-style.json` | 三路线共享字号、术语、安全区和平台遮挡参数 |
| `mechanical_video_next/text_layout.py` | 实际字体测量、语义分句、时序/碰撞/接触区域验证 |
| `remotion/src/TextOverlay.tsx` | 浏览器字体宽度、单行、溢出和层间重叠门禁 |
| `remotion/src/index.tsx` | 独立文字层；字幕单行；署名分时显示 |
| `scripts/produce.py` | 合成前风格锁/排版检查；保留旧备用音频缓存身份 |
| `mechanical_video_next/style_lock.py` | 文件保护及同姿态非文字像素差异检测 |
| `mechanical_video_next/qa_images.py` | 复用既有六项API，修复视频JPEG参数与镜头ID校验 |
| `scripts/validate_text_readability.py` | 真实视频姿态、前后渲染、手机预览和运动样片验证 |
| `tests/test_text_layout.py`, `tests/test_text_cache_boundary.py`, `tests/test_style_lock.py`, `tests/test_qa_images.py` | 对应自动化测试 |
| `.gitignore`, `remotion/tsconfig.json`, `AGENTS.md` | 共享配置白名单、JSON导入及持续风格保护要求 |

## 文字规则

1920×1080：字幕64px、章节76px、零件64px、原理64px、数字72px、辅助48px。实际手机预览后放大了名称和辅助字；保留PingFang SC Medium、白字深描边、底部居中。原字体缺失时阻止，禁止静默改字体。

标题区 `[64,38,1856,142]`，零件区 `[64,162,1856,282]`，辅助区 `[64,288,1856,360]`，原理/数字区 `[64,802,1856,914]`，字幕区 `[90,940,1830,1040]`。共用区域必须分时。可配置平台insets，默认只描述视频内部；平台UI未经验证。显式提供的机械接触区域参与碰撞检查。

8—14字为优先建议，实际字体宽度是显示门槛。能单行显示的已有整句保留原时轴；超宽句只接受保持文字顺序、术语完整、非重叠且绑定实际音频SHA的对齐。缺对齐则阻止合成，不按字数猜时长、不缩字号、不改配音速度、不重新生成正确TTS。`split_text()`只给语义建议。生产入口的音频绑定值是实际逐镜头音频SHA列表的`common.digest()`，不是配置自行声明的任意SHA。浏览器再次检查实际CSS字体宽度。

文字配置和合成源码只失效合成缓存，机械缓存键不变；旧备用say音频的处理身份固定为修改前哈希。Neil配音处理代码未修改。旧成片及冻结任务不自动升级。

## 真实结果

完整证据目录：`output/text-readability-20261113-v2/`。

- `report.json`：最终代码/配置哈希、六组真实媒体姿态回归与52个原文件保护结果。
- `independent-qa.json`：独立QA，绑定精确report SHA，记录实际压缩图读取与UNKNOWN。
- `motion.mp4`：原缓存机械镜头与原音频重合成的3秒运动诊断，1920×1080/30fps，容器3.008秒，完整解码PASS。
- `*-before.png`/`*-after.png`：同姿态分别经修改前/后文字模板渲染，本地像素检测专用，不进入视觉上下文。
- `tests.log`：87项自动化测试PASS，最终6.230秒；TypeScript typecheck及`git diff --check`通过。

六事件覆盖开场、章节、历史最长分段、密集名称、核心接触、结尾，共18个360/390/430px等比预览。独立QA分三轮实际读取三张WebP联系图，共126,546字节：采样字幕单行无溢出，章节/名称/字幕可辨，对比足够，未见文字遮挡关键接触点。57条历史字幕全量显示检查通过，最大宽1158px，小于1740px安全宽。

六组非文字回归均PASS，最大超12级像素差比例约0.00585%，低于0.5%阈值。文字遮罩704,432像素，检查约66%的画面；遮罩内机械像素不能由这项检测证明，结合原机械源文件哈希补证。52个抽查历史媒体、音频、CAD及封面文件全部未变；完整风格锁通过。正式3:4/4:3封面PNG及生成代码未改。

压缩基准`work/qa-images/validation.json`：六图1,276,147→85,308字节，减少93.3%；首次转换约0.3065秒，重复缓存命中100%。新三张联系图也100%命中重复缓存。默认WebP80，最长边按1024/1280/1600/1200分类，普通图片目标300KB，内容/代码/参数哈希缓存。实际视觉读取没有原PNG；没有把字节减少冒充视觉token减少，token无计量填null。

## 尚未解决及验收边界

| 项目 | 结果 |
|---|---|
| 原有风格与机械内容保护 | 已检源文件及六姿态PASS；未调用机械重建/渲染 |
| 新模板单行、安全区、碰撞 | PASS；超宽无对齐阻止输出 |
| 手机文字 | 18档3D诊断采样PASS，不外推整片或所有设备 |
| 全片字幕同步 | UNKNOWN；历史57段有比例切时，原33句中6句超宽，缺可信细分对齐会阻止新正式合成 |
| 精确截图对应视频版本 | UNKNOWN；已定位同题材工程与候选版本，未冒称截图级精确匹配 |
| 连续观看、听审 | UNKNOWN；解码及静帧不能替代 |
| 2D/2.5D实际手机画面 | UNKNOWN；共享配置/排版测试PASS，未对这两路重新合成真实画面 |
| 数字标注实际镜头 | UNKNOWN；已有配置和排版验证，没有专门数字镜头实查 |
| 平台UI遮挡 | UNKNOWN；未假设统一平台遮挡范围 |
| 历史分栏/烧录小字 | 未批量迁移，不宣称历史小字已全部达标 |
| 全片机械接触遮挡 | UNKNOWN；采样和显式接触区检查不代替全片 |

诊断使用统一标题/通用组件名称以测试排版，不是最终逐镜头知识标注。上述UNKNOWN阻止全片COMPLETED。没有上传、发布、保存平台草稿；增长目标和在制任务保持原授权范围。

## 复验

```sh
UV_CACHE_DIR=/private/tmp/mechanical-video-next-uv-cache uv run python scripts/validate_text_readability.py --task output/tasks/stapler-3d-20261113 --output output/text-readability-new-review
UV_CACHE_DIR=/private/tmp/mechanical-video-next-uv-cache uv run python -m unittest tests.test_qa_images tests.test_text_layout tests.test_style_lock tests.test_text_cache_boundary tests.test_pipeline tests.test_narration tests.test_repairs tests.test_multiroute tests.test_covers tests.test_nail_clipper_cache tests.test_render_budget
```

真实媒体诊断需本机订书机缓存；新检出不含历史私有视频。通用风格门禁核查共享保护文件，完整单片QA另核查本地冻结配置和CAD快照。不得为通过检测更新风格锁、改相机或重生成正确音频。
