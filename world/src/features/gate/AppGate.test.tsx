import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppGate } from "./AppGate";

let mockPathname = "/learn";
const mockReplace = vi.fn();
let mockMessenger: { provider: "telegram" | "max"; initData: string } | null = null;
const mockLogin = vi.fn();
let mockHasPlayer = true;
const mockStatus = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({ replace: mockReplace }),
}));

vi.mock("@/lib/messenger", () => ({
  detectMessenger: () => mockMessenger,
  messengerLogin: (...args: unknown[]) => mockLogin(...args),
}));

vi.mock("@/lib/v2/client", () => ({
  hasPlayer: () => mockHasPlayer,
}));

vi.mock("@/lib/v2/registration", () => ({
  registrationApi: { status: () => mockStatus() },
  RegistrationError: class RegistrationError extends Error {},
}));

const mockRemember = vi.fn();
vi.mock("@/lib/token", () => ({
  rememberPlayerToken: (...args: unknown[]) => mockRemember(...args),
}));

beforeEach(() => {
  mockPathname = "/learn";
  mockMessenger = null;
  mockHasPlayer = true;
  mockReplace.mockReset();
  mockLogin.mockReset();
  mockStatus.mockReset();
  // RegistrationFlow при монтировании сам запрашивает статус для предзаполнения
  mockStatus.mockResolvedValue({ identity: null, consents: [], is_registered: false });
  mockRemember.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AppGate", () => {
  it("зарегистрированный ученик — рендерит мир", async () => {
    mockStatus.mockResolvedValue({ identity: null, consents: [], is_registered: true });
    render(<AppGate><div>Мир открыт</div></AppGate>);
    await waitFor(() => expect(screen.getByText("Мир открыт")).toBeInTheDocument());
    expect(screen.queryByText("Анкета ученика")).not.toBeInTheDocument();
  });

  it("незарегистрированный — только флоу регистрации, мир скрыт", async () => {
    mockStatus.mockResolvedValue({ identity: null, consents: [], is_registered: false });
    render(<AppGate><div>Мир открыт</div></AppGate>);
    await waitFor(() => expect(screen.getByText("Анкета ученика")).toBeInTheDocument());
    expect(screen.queryByText("Мир открыт")).not.toBeInTheDocument();
  });

  it("Telegram: вход по initData, токен сохраняется, is_registered=true — мир", async () => {
    mockMessenger = { provider: "telegram", initData: "tg-data" };
    mockLogin.mockResolvedValue({
      id: 5, external_key: "telegram:5", display_name: "Маша Петрова",
      token: "wses.abc.def", is_registered: true,
    });
    render(<AppGate><div>Мир открыт</div></AppGate>);
    await waitFor(() => expect(screen.getByText("Мир открыт")).toBeInTheDocument());
    expect(mockLogin).toHaveBeenCalledWith("telegram", "tg-data");
    expect(mockRemember).toHaveBeenCalledWith("wses.abc.def", "telegram:5");
    expect(mockStatus).not.toHaveBeenCalled();
  });

  it("Telegram: is_registered=false — гейт регистрации с предзаполненным именем", async () => {
    mockMessenger = { provider: "telegram", initData: "tg-data" };
    mockLogin.mockResolvedValue({
      id: 5, external_key: "telegram:5", display_name: "Маша Петрова",
      token: "wses.abc.def", is_registered: false,
    });
    render(<AppGate><div>Мир открыт</div></AppGate>);
    await waitFor(() => expect(screen.getByText("Анкета ученика")).toBeInTheDocument());
    await waitFor(() =>
      expect(screen.getByPlaceholderText("Аня")).toHaveValue("Маша"),
    );
  });

  it("без мессенджера и без игрока — редирект на /onboarding", async () => {
    mockHasPlayer = false;
    render(<AppGate><div>Мир открыт</div></AppGate>);
    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/onboarding"));
    expect(screen.queryByText("Мир открыт")).not.toBeInTheDocument();
  });

  it("открытые маршруты (/legal) — без проверок", async () => {
    mockPathname = "/legal/privacy";
    render(<AppGate><div>Политика</div></AppGate>);
    await waitFor(() => expect(screen.getByText("Политика")).toBeInTheDocument());
    expect(mockStatus).not.toHaveBeenCalled();
    expect(mockLogin).not.toHaveBeenCalled();
  });
});
