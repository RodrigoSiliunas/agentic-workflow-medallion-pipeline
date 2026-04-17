# Design System — Flowertex Platform

Inspirado em **Cohere** (enterprise polish, 22px cards, chromatic restraint) e **flowertex.ai** (purple-forward, dark-first, technical warmth, generous whitespace, minimal tech aesthetic).

## 1. Visual Theme

Uma plataforma de dados que transmite **autoridade tecnica com acessibilidade**. Interface dark-first com superficies elevadas em cards arredondados. Gradientes sutis nas areas de destaque (status do pipeline, hero sections). Minimalismo funcional — cada elemento tem proposito.

**Personalidade**: Forward-thinking enterprise AI partner. Engenharia de dados encontra conversa humana. Serio o suficiente para CTOs, acessivel o suficiente para analistas. Purple comunica inovacao, grayscale comunica profissionalismo.

## 2. Color Palette

### Brand Purple (Flowertex)

| Step | Hex | Uso |
|------|-----|-----|
| `brand-50` | `#F5F3FF` | Tinted backgrounds, hover overlays light |
| `brand-100` | `#EDE9FE` | Subtle highlights |
| `brand-200` | `#DDD6FE` | Borders ativos light mode |
| `brand-300` | `#C4B5FD` | Disabled states |
| `brand-400` | `#A78BFA` | Hover dark mode |
| `brand-500` | `#8E51F6` | Brand secondary, badges |
| `brand-600` | `#7F22FE` | **Brand primary** — botoes principais, links, focus rings |
| `brand-700` | `#7008E7` | Active/pressed states |
| `brand-800` | `#5B0FB7` | Dark accents |
| `brand-900` | `#3B0764` | Deep contrast |

### Dark Mode (Primary)

| Role | Color | Hex | Uso |
|------|-------|-----|-----|
| **Background** | Near Black | `#090A0B` | Fundo principal da aplicacao |
| **Surface** | Slate 950 | `#18181B` | Cards, sidebar, containers |
| **Surface Elevated** | Slate 800 | `#272A2E` | Cards hover, modais, dropdowns |
| **Border** | Slate 700 | `#3F3F46` | Bordas de cards e separadores |
| **Border Subtle** | Slate 600 | `#52525B` | Bordas secundarias |
| **Text Primary** | Zinc 50 | `#FAFAFA` | Texto principal |
| **Text Secondary** | Zinc 400 | `#A1A1AA` | Texto secundario, placeholders |
| **Text Tertiary** | Zinc 500 | `#71717A` | Labels, captions, timestamps |

### Light Mode

| Role | Color | Hex | Uso |
|------|-------|-----|-----|
| **Background** | Zinc 50 | `#FAFAFA` | Fundo principal |
| **Surface** | White | `#FFFFFF` | Cards |
| **Surface Elevated** | Zinc 100 | `#F4F4F5` | Cards hover |
| **Border** | Zinc 200 | `#E4E4E7` | Bordas de cards |
| **Border Subtle** | Zinc 300 | `#D4D4D8` | Bordas secundarias |
| **Text Primary** | Zinc 900 | `#18181B` | Texto principal |
| **Text Secondary** | Zinc 600 | `#52525B` | Texto secundario |
| **Text Tertiary** | Zinc 500 | `#71717A` | Labels, captions |

### Status Colors

| Role | Color | Hex | Uso |
|------|-------|-----|-----|
| **Success** | Emerald 500 | `#10B981` | Pipeline SUCCESS, validacao OK |
| **Error** | Red 500 | `#EF4444` | Pipeline FAILED, erros |
| **Warning** | Amber 500 | `#F59E0B` | RUNNING, pendencias |
| **Info** | Blue 500 | `#3B82F6` | Informacoes, links |

### Pipeline Status Colors

| Status | Color | Badge |
|--------|-------|-------|
| SUCCESS | `#10B981` | Filled emerald dot |
| FAILED | `#EF4444` | Filled red dot |
| RUNNING | `#F59E0B` | Animated amber pulse |
| IDLE | `#71717A` | Hollow zinc dot |
| RECOVERED | `#3B82F6` | Blue dot |

## 3. Typography

### Font Stack

| Role | Font | Fallback |
|------|------|----------|
| **Display/Headlines** | `Geist` | `system-ui, -apple-system, sans-serif` |
| **Body/UI** | `Geist` | `system-ui, -apple-system, sans-serif` |
| **Code** | `Geist Mono` | `JetBrains Mono, Fira Code, Consolas, monospace` |

Geist eh a font da Flowertex (e da Vercel). Carregada via `@nuxt/fonts` provider Google. Pesos disponiveis: 100, 200, 300, 400, 500, 600, 700, 800, 900.

### Hierarchy

| Role | Size | Weight | Line Height | Letter Spacing |
|------|------|--------|-------------|----------------|
| Display | `clamp(32px, 7vw, 64px)` | 500 | 1.05 | -0.04em |
| Heading 1 | 36px | 600 | 1.1 | -0.03em |
| Heading 2 | 28px | 600 | 1.2 | -0.02em |
| Heading 3 | 22px | 600 | 1.25 | -0.015em |
| Heading 4 | 18px | 600 | 1.3 | -0.01em |
| Body | 15px | 400 | 1.6 | normal |
| Body Small | 13px | 400 | 1.5 | normal |
| Caption | 12px | 400 | 1.4 | normal |
| Code | 13px | 400 | 1.5 | normal |
| Overline | 11px | 600 | 1.3 | 0.08em (uppercase) |

Headings com **negative tracking** (`-0.01em` a `-0.04em`) eh signature Flowertex — comunica autoridade tecnica.

## 4. Spacing

Base unit: **4px**

| Token | Value | Uso |
|-------|-------|-----|
| `xs` | 4px | Gaps entre icones e labels |
| `sm` | 8px | Padding interno minimo |
| `md` | 12px | Padding de botoes, gap de grid |
| `lg` | 16px | Padding de cards |
| `xl` | 24px | Separacao entre secoes |
| `2xl` | 32px | Margem entre blocos |
| `3xl` | 48px | Espacamento entre secoes da pagina |
| `4xl` | 64px | Hero sections |
| `5xl` | 96px | Hero vertical breathing room (Flowertex generous whitespace) |

## 5. Border Radius

| Token | Value | Uso |
|-------|-------|-----|
| `sm` | 6px | Inputs, small badges, tags |
| `md` | 10px | Botoes, dropdowns |
| `lg` | 16px | Cards padrao, modais |
| `xl` | 22px | Cards destacados (Cohere signature) |
| `2xl` | 28px | Hero cards |
| `full` | 9999px | Avatares, pills, status dots, CTAs Flowertex (`rounded-full` buttons) |

CTAs principais usam `rounded-full` — outra signature Flowertex.

## 6. Shadows

### Dark mode (sutis)

| Level | Shadow | Uso |
|-------|--------|-----|
| None | — | Maioria dos elementos (bordas definem) |
| Subtle | `0 1px 2px rgba(0,0,0,0.4)` | Dropdowns, tooltips |
| Medium | `0 4px 12px rgba(0,0,0,0.5)` | Modais, popovers |
| Inner Glow | `inset 70px -20px 130px 0px rgba(127, 34, 254, 0.05)` | Feature cards (Flowertex inset shadow signature) |
| Focus | `0 0 0 2px rgba(127, 34, 254, 0.4)` | Focus ring (brand-600 com alpha) |

Em dark mode, profundidade vem de **cor de fundo** (card mais claro = mais elevado), nao de sombra.

### Light mode

| Level | Shadow | Uso |
|-------|--------|-----|
| Subtle | `0 1px 2px rgba(0,0,0,0.05)` | Dropdowns |
| Medium | `0 4px 12px rgba(0,0,0,0.08)` | Modais, popovers |
| Card | `0 1px 3px rgba(0,0,0,0.1)` | Cards padrao |
| Focus | `0 0 0 2px rgba(127, 34, 254, 0.2)` | Focus ring |

## 7. Hero Signature (Flowertex)

A homepage do `flowertex.ai` tem dois elementos visuais que sao signature:

### Gradient Blur Circles

```css
.hero-blur-purple {
  position: absolute;
  width: 600px;
  height: 600px;
  background: rgba(127, 34, 254, 0.15);
  filter: blur(200px);
  border-radius: 50%;
  pointer-events: none;
}
```

Posicionar absolutamente atras de hero sections para criar profundidade colorida sem dominar.

### Grid Background Pattern

```css
.hero-grid {
  background-image:
    linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px);
  background-size: 64px 64px;
}
```

Pattern sutil de grid no background, comunica precisao de engenharia.

## 8. Component Patterns

### Botoes

| Variante | Background | Text | Borda | Radius |
|----------|-----------|------|-------|--------|
| Primary | `brand-600` | White | none | `full` (CTA) ou `md` (UI) |
| Secondary | Transparent | `text-primary` | `1px solid border` | `md` |
| Ghost | Transparent | `text-secondary` | none | `md` |
| Danger | Red 500 | White | none | `md` |

Hover: lighten 10%. Active: darken 5%. Disabled: 40% opacity.
Padding: `8px 16px` (md) / `10px 20px` (lg) / `12px 24px` (xl CTA).

### Cards

```
Background: surface (var(--surface))
Border: 1px solid var(--border)
Border-radius: lg (16px) ou xl (22px) para destaque
Padding: 16px-24px
Hover: surface-elevated
```

### Chat Bubbles

| Tipo | Background | Border-radius |
|------|-----------|---------------|
| User | `brand-600` | `16px 16px 4px 16px` |
| Assistant | `surface` | `16px 16px 16px 4px` |

### Sidebar (claude.ai-style)

```
Width: 280px (desktop), collapsa em mobile
Background: var(--surface)
Border-right: 1px solid var(--border)
Sections: header user → new thread CTA → thread list → pipelines → footer
Thread item hover: surface-elevated
Active thread: bg surface-elevated + left border 2px solid brand-600
```

### Inputs

```
Background: var(--surface)
Border: 1px solid var(--border)
Border-radius: sm (6px)
Focus: border brand-600 + focus ring
Placeholder: text-tertiary
Text: text-primary
```

### Status Badge

```
Dot (8px circle) + label text
SUCCESS: status-success dot + "Active" / "OK"
FAILED: status-error dot + "Falhou"
RUNNING: status-warning animated pulse + "Rodando"
IDLE: text-tertiary hollow dot + "Inativo"
```

### Action Cards (no chat)

```
Background: surface-elevated
Border: 1px solid border-subtle
Border-radius: lg (16px)
Left accent: 3px solid [color based on action type]
  PR created: brand-600
  Run triggered: warning
  Query executed: info
Padding: 12px 16px
```

## 9. Layout

### Sidebar + Chat (2 colunas)

```
|-- 280px sidebar --|------------ flex-1 chat area -----------|
|                   |                                         |
|  User header      |  Workflow header                        |
|  + New thread     |  Status badge + actions                 |
|                   |                                         |
|  Today            |  Message list (scroll)                  |
|  • thread A       |  ...messages...                         |
|  • thread B       |                                         |
|                   |                                         |
|  Last 7 days      |                                         |
|  • thread C       |                                         |
|                   |                                         |
|  --- Pipelines -- |                                         |
|  ▸ medallion      |                                         |
|  + Deploy         |                                         |
|                   |                                         |
|  Settings         |  Chat input (fixed bottom)              |
|  Logout           |                                         |
```

### Settings (tabs)

```
|-- 280px sidebar --|-- 200px tab nav --|-- flex-1 content ---|
|                   |  Geral            |  [Settings form]    |
|                   |  Credenciais      |                     |
|                   |  Canais           |                     |
|                   |  Usuarios         |                     |
```

## 10. Motion

| Tipo | Duration | Easing |
|------|----------|--------|
| Hover | 150ms | ease-out |
| Expand/Collapse | 200ms | ease-in-out |
| Modal enter | 200ms | ease-out |
| Modal exit | 150ms | ease-in |
| Page transition | 200ms | ease-in-out |
| Streaming cursor | 500ms | linear (blink) |
| Status pulse | 1500ms | ease-in-out infinite |

## 11. Agent Prompt Guide

Ao pedir componentes ao LLM, use estas referencias:

- "Card padrao: background var(--surface), border 1px solid var(--border), radius 16px, padding 16px"
- "Botao primario CTA: bg brand-600 (#7F22FE), text white, radius full, padding 12px 24px, font-medium"
- "Botao primario UI: bg brand-600, text white, radius 10px, padding 8px 16px"
- "Status badge SUCCESS: dot #10B981 8px + texto"
- "Chat bubble usuario: bg brand-600, radius 16 16 4 16"
- "Chat bubble assistente: bg surface, radius 16 16 16 4"
- "Sidebar: width 280px, bg surface, border-right border"
- "Heading display: Geist clamp(32px,7vw,64px) weight 500, tracking -0.04em"
- "Heading H2: Geist 28px weight 600, tracking -0.02em"
- "Body: Geist 15px weight 400, line-height 1.6"
- "Code block: Geist Mono 13px, bg #090A0B, radius 10px, padding 16px"
- "Hero blur signature: rgba(127,34,254,0.15) com filter blur(200px), 600x600px absolute"
