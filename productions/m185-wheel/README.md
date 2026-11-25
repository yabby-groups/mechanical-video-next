# 鼠标滚轮怎么知道你往哪边滚

## 型号与证据

- 产品参考罗技 M185 外观。检查了 Logitech 产品图，以及 iFixit 滚轮更换指南开头的整机和拆壳照片。 [Logitech M185](https://www.logitech.com/en-us/shop/p/m185-wireless-mouse) · [滚轮更换指南](https://www.ifixit.com/Guide/Logitech+M185+Wireless+Mouse+Scroll+Wheel+Replacement/171931)
- 查看了滚轮更换指南第 4–6 步和主板更换指南的拆轮照片。画面据此还原上壳、线路板、两键微动开关、滚轮和轴端编码器的位置关系。拆开后以轴端抽出和重新插入的动画展示传动路径。外壳曲面和板上次要零件采用近似造型。 [滚轮更换第 4 步](https://www.ifixit.com/Guide/Logitech+M185+Wireless+Mouse+Scroll+Wheel+Replacement/171931#s366399) · [主板更换指南](https://www.ifixit.com/Guide/Logitech+M185+Wireless+Mouse+Motherboard+Replacement/179853)
- 放大段使用通用接触式正交编码器的教学模型。参考两路增量输出、公共端和相位错开的输出图。M185 拆解照片可见轴端编码器外壳，原件内部的触点形状和每格转角没有实物测量。 [Alps Alpine EC10E1220505](https://tech.alpsalpine.com/e/products/detail/EC10E1220505/) · [Bourns PEC11R 数据表](https://www.bourns.com/docs/product-datasheets/pec11r.pdf)

## 镜头

- **00:00–00:05.47** 鼠标和网页同框，从滚轮高亮的一条刻线和网页卡片的位置读出联动。顺拨两次后留出观察间隔，第 3.36 秒开始反拨，网页回到起点，引出方向判断。
- **00:05.47–00:16.20** 移开上壳，推近轴端和编码器，给出轴端退出、入座和跟转的运动。
- **00:16.20–00:26.90** 移开冲压金属盖，露出固定触片和转盘。转盘沿轴转动，触片末端贴着盘面，依次扫过镀层导电区和绝缘间隔。旁边的指示灯显示各路与公共端的导通状态。
- **00:26.90–00:43.67** 保持相同机位，连续呈现顺拨时 00 → 10 → 11 → 01 → 00，反拨时 00 → 01 → 11 → 10 → 00。两位分别表示甲、乙两路的导通状态。
- **00:43.67–00:55.60** 回到整机对照网页进退，串联滚轮转动、信号顺序与方向判断。

全片三维画面和网页为本集制作，拆解资料用于参考。声音由项目现有 Neil 配音、合成滚动拟音和 CC0《Quiet Link – Technology》配乐组成。 [旁白](narration.txt) · [剪辑设置](edit.json) · [配乐许可](../../assets/audio/bgm/starter/CC0.md)
