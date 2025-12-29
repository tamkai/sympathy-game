# Sympathy Game - Design System
> **Version**: 1.0
> **Role**: Designer
> **Concept**: "Pop & Glassy"

## 1. Brand Identity
### Core Values
*   **Empathy (共感)**: 暖かさ、つながり。
*   **Gap (ズレ)**: ユニークさ、驚き、笑い。
*   **Aesthetic (美学)**: 洗練された、所有したくなる美しさ。

### Logo / Icon Concept
*   **Symbol**: "Pink Cow" (サングラスをかけたピンクの牛)。
*   **Style**: フラットアイコンだが、Glassmorphism背景に乗ることで浮遊感を演出。

---

## 2. Color Palette
### Primary Colors
*   **Sympathy Pink**: `#FF6B95` - "Pink Cow"の色。アクションボタン、アクセント。
*   **Deep Violet**: `#2D1B4E` - ベースのテキスト色、強めの影。

### Background (Gradients)
*   **Liquid Gradient**: 流体的に変化するグラデーション。
    *   Start: `#F8CEDA` (Pale Pink)
    *   Mid: `#D4D3FF` (Periwinkle)
    *   End: `#EBEBEB` (White Smoke)
    *   *Usage*: body background, animated with CSS keyframes.

### Glassmorphism (Cards)
*   **Glass Surface**:
    *   Background: `rgba(255, 255, 255, 0.25)`
    *   Border: `1px solid rgba(255, 255, 255, 0.5)`
    *   Backdrop Filter: `blur(12px)`
    *   Shadow: `0 8px 32px 0 rgba(31, 38, 135, 0.15)`

---

## 3. Typography
### Font Family
*   **Japanese**: `"Noto Sans JP", sans-serif` (Weight: 400, 700)
    *   *Reason*: 視認性が高く、モダンでニュートラル。
*   **English / Numbers**: `"Outfit", sans-serif` or `"Inter", sans-serif`
    *   *Reason*: Outfitは少しポップで丸みがあり、ゲームの雰囲気に合う。

### Scale
*   **H1 (Title)**: 32px / Bold / LS 0.05em
*   **H2 (Section)**: 24px / Bold
*   **Body**: 16px / Regular / LH 1.6
*   **Tag / Caption**: 12px / Medium

---

## 4. UI Components
### Buttons
*   **Primary Button**:
    *   Bg: Sympathy Pink (`#FF6B95`)
    *   Text: White
    *   Shape: Rounded Pill (Border-radius: 999px)
    *   Effect: Hoverで少し浮き上がる + Glow効果。
*   **Secondary Button**:
    *   Bg: Glass Surface
    *   Border: White
    *   Text: Deep Violet

### Inputs
*   **Glass Input**:
    *   Bg: `rgba(255, 255, 255, 0.4)`
    *   Border: None (Or very subtle white)
    *   Focus: White border + Bloom effect.

### Feedback (Modal/Toast)
*   **Correct (Sympathy!)**: Rainbow Gradient Border + 紙吹雪エフェクト。
*   **Incorrect (Pink Cow)**: 画面全体が一瞬ピンクにフラッシュ + 牛の鳴き声（"Moo!"）。

---

## 5. Animation (Micro-interactions)
*   **Hover**: 全てのインタラクティブ要素は、Hover時に Scale (1.05) または Brightness の変化を伴う。
*   **Page Transition**: ふわっと浮き上がるような Fade In Up。
*   **Loading**: 牛が咀嚼する（モグモグ）アニメーション、またはミルクが波打つローダー。
