import "@testing-library/jest-dom/vitest";
import { mockWindows } from "@tauri-apps/api/mocks";
import { vi } from "vitest";

// Provide a Tauri window context for all tests
mockWindows("main");

// Stub window.matchMedia (not available in happy-dom)
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Stub CSS custom properties used in components
const style = document.createElement("style");
style.textContent = `
  :root {
    --accent: #007aff;
    --accent-subtle: rgba(0,122,255,0.1);
    --glass: rgba(255,255,255,0.08);
    --glass-raised: rgba(255,255,255,0.12);
    --glass-inset: rgba(0,0,0,0.06);
    --glass-border: rgba(255,255,255,0.1);
    --glass-blur: blur(20px);
    --text: #fff;
    --text-2: rgba(255,255,255,0.7);
    --text-3: rgba(255,255,255,0.4);
    --error: #ff453a;
    --error-subtle: rgba(255,69,58,0.1);
    --success: #30d158;
    --warning: #ff9f0a;
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.2);
    --shadow-xl: 0 20px 60px rgba(0,0,0,0.4);
    --font-sans: system-ui;
    --font-mono: monospace;
  }
`;
document.head.appendChild(style);
