# Design System Master File — XTeink Brand

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** XTeink · 抖音UID采集
**© 2026 阅星曈 v1.2.0**
**Generated:** 2026-05-26
**Category:** Desktop Utility Tool

---

## Global Rules

### Color Palette (XTeink Brand)

| Role | Hex | Usage |
|------|-----|-------|
| Primary | `#171717` | Text, headings |
| Accent | `#FF6600` | CTA buttons, focus rings, loading state (logo orange dot) |
| Background | `#FAFAFA` | App shell |
| Card | `#FFFFFF` | Content card |
| Border | `#E5E5E5` | Inputs, dividers |
| Text Muted | `#525252` | Subtitles, hints |
| Footer | `#737373` | Author, version |

### Typography

- **Heading / Body:** Inter, Segoe UI, Microsoft YaHei UI
- **Monospace (UID result):** Consolas, Cascadia Mono, JetBrains Mono
- **Mood:** minimal, clean, professional, tech-oriented

### Spacing

| Token | Value | Usage |
|-------|-------|-------|
| `--space-sm` | `8px` | Inline gaps |
| `--space-md` | `16px` | Standard padding |
| `--space-lg` | `24px` | Outer margins |
| `--space-xl` | `28px` | Window padding |

### Layout Pattern

- **Pattern:** Minimal Single Column
- **Header:** XTeink logo + tagline + subtitle
- **Body:** Single card with input, actions, result
- **Footer:** © 2026 阅星曈 v1.2.0 (right-aligned, subtle)

---

## Component Specs

### Primary Button
- Background: `#FF6600`, hover `#E55A00`
- White text, 10px radius, 600 weight

### Secondary Button
- White bg, `#E5E5E5` border, hover orange border + `#FFF7ED` bg

### Inputs
- 10px radius, focus border `#FF6600`

---

## Anti-Patterns

- ❌ Rose/pink palette (replaced by XTeink black + orange)
- ❌ Emojis as icons
- ❌ Layout-shifting hovers
- ❌ Low contrast muted text
