# Third-party notices

Original Workshop code is Apache-2.0. Only the following visual functions are adapted from Pixel Agents, pinned to **d1e007a9fdf3003c252d2973abe1999ae59aec33**:

- [`webview-ui/src/office/projection.ts`](https://github.com/pixel-agents-hq/pixel-agents/blob/d1e007a9fdf3003c252d2973abe1999ae59aec33/webview-ui/src/office/projection.ts): `mapOffset` and `overlayProjection` → `frontend/src/scene/geometry.ts`. Retains integer-device-pixel centering and common DOM/canvas coordinate conversion; locally typed and independent of upstream types.
- [`webview-ui/src/office/sprites/spriteCache.ts`](https://github.com/pixel-agents-hq/pixel-agents/blob/d1e007a9fdf3003c252d2973abe1999ae59aec33/webview-ui/src/office/sprites/spriteCache.ts): the `getCachedSprite` opaque-pixel raster loop → `drawPixels` in `frontend/src/scene/pixels.ts`. Draws directly at a passed origin with immutable sprite input; no DOM cache or imported artwork.

These exact modules and the [licence](https://github.com/pixel-agents-hq/pixel-agents/blob/d1e007a9fdf3003c252d2973abe1999ae59aec33/LICENSE) were read through `gh api` before extraction. No upstream server, hooks, PTY, authentication, runtime heuristics, timers or assets are included. Character art is original Workshop code-drawn pixel art. The renderer is stationary and projection-driven.

## Pixel Agents licence (verbatim)

MIT License

Copyright (c) 2026 Pablo De Lucca

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
