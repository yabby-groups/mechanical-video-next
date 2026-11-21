# Notice and attributions

## shot-director

The camera-move vocabulary, the six-layer shot structure, the prompt templates and the choose-by-feeling / choose-by-scene cheat sheets follow the structure of Adrian Punk's two-part Chinese guide to AI video camera movement:

- Part 1: https://x.com/AdrianPunk115/status/2104172387575222768
- Part 2: https://x.com/AdrianPunk115/status/2104523576020017575
- Author: [@AdrianPunk115](https://x.com/AdrianPunk115)

The text in this repository is an English adaptation written from scratch with new examples; no text or images from the original articles are reproduced. Credit for the original structure belongs to the author. The chapter on directing time and space, the review format and the depth-renderer mapping are original to this repository.

## Images in `assets/`

The cover and figures were made for this repository. The film frames come from HOME, rendered by the author of this repository from still images the author generated. HOME's three opening images by [@martianprompts](https://x.com/martianprompts) are not included anywhere in this repository.

## still-to-film

Demo assets in `skills/still-to-film/templates/` are generated procedurally by scripts in this repository.

`references/blender-route.md` (headless Blender, the target-frame and test-still loop, the lead + one builder split) and the social-delivery notes in `references/finishing.md` (first frame as thumbnail, 4:5, watermark placement, spectrogram check, -16 LUFS) are adapted from Mr Tactical's article "How to make Claude build 3D videos in Blender":

- https://x.com/MrTacticalX/status/2116626031494705365
- Author: [@MrTacticalX](https://x.com/MrTacticalX)

The text here is rewritten and merged with this repository's own pipeline; no text from the article is reproduced.

`references/footage-as-light.md` generalises the method shown in aicreataro's making-of post (AI video projected onto a white 3D statue by two projector lights in a dark, hazy hall):

- https://x.com/aicreataro/status/2121141326745903352
- Author: [@aicreataro](https://x.com/aicreataro)

The write-up, the role split and the review list are this repository's own; the specific tools named in the post are not required.

The scripts call, but do not include, these projects (each under its own license):

- HyperFrames (https://github.com/heygen-com/hyperframes)
- GSAP (https://github.com/greensock/GSAP)
- Depth Anything V2 (https://github.com/DepthAnything/Depth-Anything-V2)
- Swin2SR (https://github.com/mv-lab/swin2sr)
- Hugging Face Transformers (https://github.com/huggingface/transformers)
- OpenCV (https://github.com/opencv/opencv)
- FFmpeg (https://github.com/FFmpeg/FFmpeg)
- Blender (https://github.com/blender/blender)

Model weights downloaded at runtime are subject to their own licenses; check the model cards before commercial use (Depth Anything V2 Large in particular has a non-commercial license).
