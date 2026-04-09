# Design System — Namastex Platform

Inspirado em **Cohere** (enterprise polish, 22px cards, chromatic restraint) e **ngrok** (dark-first, technical warmth, generous whitespace).

## 1. Visual Theme

Uma plataforma de dados que transmite **autoridade tecnica com acessibilidade**. Interface dark-first com superficies elevadas em cards arredondados. Gradientes sutis nas areas de destaque (status do pipeline, hero sections). Minimalismo funcional — cada elemento tem proposito.

**Personalidade**: Engenharia de dados encontra conversa humana. Serio o suficiente para CTOs, acessivel o suficiente para analistas.

## 2. Color Palette

### Dark Mode (Primary)

| Role | Color | Hex | Uso |
|------|-------|-----|-----|
| **Background** | Near Black | `#0f0f12` | Fundo principal da aplicacao |
| **Surface** | Dark Card | `#1a1a22` | Cards, sidebar, containers |
| **Surface Elevated** | Elevated Card | `#24242e` | Cards hover, modais, dropdowns |
| **Border** | Dark Border | `#2e2e3a` | Bordas de cards e separadores |
| **Border Subtle** | Subtle Border | `#3a3a48` | Bordas secundarias |
| **Text Primary** | White | `#f0f0f5` | Texto principal |
| **Text Secondary** | Muted | `#8b8b9e` | Texto secundario, placeholders |
| **Text Tertiary** | Dimmed | `#5a5a6e` | Labels, captions, timestamps |

### Light Mode

| Role | Color | Hex | Uso |
|------|-------|-----|-----|
| **Background** | White | `#ffffff` | Fundo principal |
| **Surface** | Snow | `#fafafa` | Cards |
| **Surface Elevated** | Light Gray | `#f2f2f5` | Cards hover |
| **Border** | Cool Border | `#d9d9dd` | Bordas de cards |
| **Text Primary** | Near Black | `#0f0f12` | Texto principal |
| **Text Secondary** | Slate | `#6b6b7e` | Texto secundario |

### Accent Colors

| Role | Color | Hex | Uso |
|------|-------|-----|-----|
| **Brand Primary** | Namastex Purple | `#7c5cfc` | Botoes primarios, links, brand |
| **Brand Hover** | Purple Light | `#9b7eff` | Hover de elementos interativos |
| **Success** | Green | `#22c55e` | Pipeline SUCCESS, validacao OK |
| **Error** | Red | `#ef4444` | Pipeline FAILED, erros |
| **Warning** | Amber | `#f59e0b` | RUNNING, pendencias |
| **Info** | Blue | `#3b82f6` | Informacoes, links |

### Pipeline Status Colors

| Status | Color | Badge |
|--------|-------|-------|
| SUCCESS | `#22c55e` | Filled green dot |
| FAILED | `#ef4444` | Filled red dot |
| RUNNING | `#f59e0b` | Animated amber pulse |
| IDLE | `#5a5a6e` | Hollow gray dot |
| RECOVERED | `#3b82f6` | Blue dot |

## 3. Typography

### Font Stack

| Role | Font | Fallback |
|------|------|----------|
| **Display/Headlines** | `Inter` | `system-ui, -apple-system, sans-serif` |
| **Body/UI** | `Inter` | `system-ui, -apple-system, sans-serif` |
| **Code** | `JetBrains Mono` | `Fira Code, Consolas, monospace` |

Usando Inter como fonte unica (via @nuxt/fonts) — clean, legivel, otima para dados.

### Hierarchy

| Role | Size | Weight | Line Height | Letter Spacing |
|------|------|--------|-------------|----------------|
| Display | 36px | 700 | 1.1 | -0.5px |
| Heading 1 | 28px | 600 | 1.2 | -0.3px |
| Heading 2 | 22px | 600 | 1.25 | -0.2px |
| Heading 3 | 18px | 600 | 1.3 | normal |
| Body | 15px | 400 | 1.6 | normal |
| Body Small | 13px | 400 | 1.5 | normal |
| Caption | 12px | 400 | 1.4 | 0.1px |
| Code | 13px | 400 | 1.5 | normal |
| Overline | 11px | 600 | 1.3 | 0.8px (uppercase) |

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

## 5. Border Radius

| Token | Value | Uso |
|-------|-------|-----|
| `sm` | 6px | Inputs, small badges, tags |
| `md` | 10px | Botoes, dropdowns |
| `lg` | 16px | Cards padrao, modais |
| `xl` | 22px | Cards destacados (Cohere signature) |
| `full` | 9999px | Avatares, pills, status dots |

## 6. Shadows (dark mode — sutis)

| Level | Shadow | Uso |
|-------|--------|-----|
| None | — | Maioria dos elementos (bordas definem) |
| Subtle | `0 1px 2px rgba(0,0,0,0.3)` | Dropdowns, tooltips |
| Medium | `0 4px 12px rgba(0,0,0,0.4)` | Modais, popovers |
| Focus | `0 0 0 2px #7c5cfc40` | Focus ring |

Em dark mode, profundidade vem de **cor de fundo** (card mais claro = mais elevado), nao de sombra.

## 7. Component Patterns

### Botoes

| Variante | Background | Text | Borda |
|----------|-----------|------|-------|
| Primary | `#7c5cfc` | White | none |
| Secondary | Transparent | `#f0f0f5` | `1px solid #2e2e3a` |
| Ghost | Transparent | `#8b8b9e` | none |
| Danger | `#ef4444` | White | none |

Hover: lighten 10%. Active: darken 5%. Disabled: 40% opacity.
Border-radius: `md` (10px). Padding: `8px 16px`.

### Cards

```
Background: Surface (#1a1a22)
Border: 1px solid #2e2e3a
Border-radius: lg (16px) ou xl (22px) para destaque
Padding: 16px-24px
Hover: Surface Elevated (#24242e)
```

### Chat Bubbles

| Tipo | Background | Border-radius |
|------|-----------|---------------|
| User | `#7c5cfc` (brand) | `16px 16px 4px 16px` |
| Assistant | `#1a1a22` (surface) | `16px 16px 16px 4px` |

### Sidebar

```
Width: 280px (desktop), collapsa em mobile
Background: Surface (#1a1a22)
Border-right: 1px solid #2e2e3a
Pipeline item: hover → Surface Elevated
Active thread: left border 2px solid #7c5cfc
```

### Inputs

```
Background: #1a1a22
Border: 1px solid #2e2e3a
Border-radius: sm (6px)
Focus: border-color #7c5cfc + focus ring
Placeholder: #5a5a6e
Text: #f0f0f5
```

### Status Badge

```
Dot (8px circle) + label text
SUCCESS: #22c55e dot + "OK" text
FAILED: #ef4444 dot + "Falhou" text
RUNNING: #f59e0b animated pulse dot + "Rodando" text
```

### Action Cards (no chat)

```
Background: Surface Elevated (#24242e)
Border: 1px solid #3a3a48
Border-radius: lg (16px)
Left accent: 3px solid [color based on action type]
  PR created: #7c5cfc (brand)
  Run triggered: #f59e0b (warning)
  Query executed: #3b82f6 (info)
Padding: 12px 16px
```

## 8. Layout

### Sidebar + Chat (2 colunas)

```
|-- 280px sidebar --|------------ flex-1 chat area -----------|
|                   |                                         |
|  Pipeline list    |  Thread header                          |
|  Thread list      |  Message list (scroll)                  |
|  + New thread     |  ...messages...                         |
|                   |  Chat input (fixed bottom)              |
|                   |                                         |
```

### Settings (tabs)

```
|-- 280px sidebar --|-- 200px tab nav --|-- flex-1 content ---|
|                   |  Geral            |  [Settings form]    |
|                   |  Credenciais      |                     |
|                   |  Canais           |                     |
|                   |  Usuarios         |                     |
```

## 9. Motion

| Tipo | Duration | Easing |
|------|----------|--------|
| Hover | 150ms | ease-out |
| Expand/Collapse | 200ms | ease-in-out |
| Modal enter | 200ms | ease-out |
| Modal exit | 150ms | ease-in |
| Page transition | 200ms | ease-in-out |
| Streaming cursor | 500ms | linear (blink) |

## 10. Agent Prompt Guide

Ao pedir componentes ao LLM, use estas referencias:

- "Card padrao: background #1a1a22, border 1px solid #2e2e3a, radius 16px, padding 16px"
- "Botao primario: bg #7c5cfc, text white, radius 10px, padding 8px 16px"
- "Status badge SUCCESS: dot #22c55e 8px + texto"
- "Chat bubble usuario: bg #7c5cfc, radius 16 16 4 16"
- "Chat bubble assistente: bg #1a1a22, radius 16 16 16 4"
- "Sidebar: width 280px, bg #1a1a22, border-right #2e2e3a"
- "Heading: Inter 22px weight 600, color #f0f0f5, letter-spacing -0.2px"
- "Body: Inter 15px weight 400, color #f0f0f5, line-height 1.6"
- "Code block: JetBrains Mono 13px, bg #0f0f12, radius 10px, padding 16px"
